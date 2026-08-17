import json
import traceback
from collections import defaultdict
from typing import AsyncGenerator

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage
from sse_starlette.sse import EventSourceResponse

from app.agent.graph import agent_graph, reset_llm_cache
from app.dashboard import build_dashboard
from app.schemas import ChatRequest, DashboardResponse


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(title="kubefriend", version="0.1.0")

# CORS middleware — allows the React app on :5173 to call this API on :8000.
# Without this, browsers block cross-origin requests for security.
# In production (docker compose), nginx proxies /api/ so both are same-origin
# and CORS is not needed — but we keep it here for local dev without Docker.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


# ── In-memory conversation store ─────────────────────────────────────────────
#
# WHY a conversation store?
# -------------------------
# LangGraph is stateless by default — each .ainvoke() call is independent.
# To support multi-turn chat ("What about the other pod?"), we need to
# remember previous messages.
#
# conversation_store maps:  conversation_id → list of past messages
#
# On each request we:
# 1. Look up the conversation_id to get previous messages
# 2. Append the new user message
# 3. Run the agent with the full history
# 4. Store the agent's response back into the store
#
# defaultdict(list) means accessing a new key automatically returns []
# instead of raising a KeyError.
#
# LIMITATION: this is in-memory only. Restarting the server loses all history.
# Sufficient for v1 — use LangGraph's built-in checkpointer for persistence later.

conversation_store: dict[str, list] = defaultdict(list)


# ── Health check ─────────────────────────────────────────────────────────────

@app.get("/healthz")
async def healthz():
    """
    Health check endpoint.
    Docker Compose, load balancers, and readiness probes call this to verify
    the service is alive. Returns immediately with no side effects.
    """
    import os
    return {"status": "ok", "llm_provider": os.getenv("LLM_PROVIDER", "openai")}


# ── LLM management endpoints ─────────────────────────────────────────────────

@app.get("/api/llm")
async def get_llm_info():
    """Return the currently active LLM provider."""
    import os
    return {"provider": os.getenv("LLM_PROVIDER", "openai")}


@app.post("/api/llm/reset")
async def reset_llm(provider: str | None = None):
    """
    Reset the LLM cache so the next chat request picks up a fresh instance.

    Optionally accepts ?provider=openai|watsonx|ollama to switch the provider
    at runtime (sets LLM_PROVIDER env var in this process).

    Used by `./kubefriend llm <provider>` to hot-swap without restarting.
    """
    import os
    if provider:
        os.environ["LLM_PROVIDER"] = provider
    reset_llm_cache()
    return {"status": "reset", "provider": os.getenv("LLM_PROVIDER", "openai")}


# ── Dashboard endpoint ────────────────────────────────────────────────────────

@app.get("/api/dashboard", response_model=DashboardResponse)
async def dashboard(namespace: str = Query("default", description="Kubernetes namespace to scan")):
    """
    Scan all pods in the given namespace, classify their health, and return
    AI-generated diagnosis and suggestions for any unhealthy pods.

    The frontend polls this endpoint every 30 seconds to keep the dashboard live.
    """
    result = await build_dashboard(namespace)
    return result


# ── Chat endpoint ─────────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    Main chat endpoint. Accepts a user message, runs the LangGraph agent,
    and streams back SSE events as the agent thinks and calls tools.

    WHY EventSourceResponse?
    ------------------------
    FastAPI's normal return is a single JSON response — the function runs,
    returns a value, connection closes.

    EventSourceResponse wraps an async generator. It:
    1. Sets Content-Type: text/event-stream (tells the browser this is SSE)
    2. Keeps the connection open
    3. Calls next() on the generator repeatedly
    4. Pushes each yielded value to the browser immediately
    5. Closes the connection when the generator is exhausted

    The browser receives events one by one as they're yielded.
    """
    return EventSourceResponse(
        _stream_agent(request.message, request.conversation_id),
        media_type="text/event-stream",
    )


# ── SSE streaming generator ───────────────────────────────────────────────────

async def _stream_agent(
    user_message: str,
    conversation_id: str,
) -> AsyncGenerator[str, None]:
    """
    Async generator that runs the LangGraph agent and yields SSE events.

    HOW async generators work:
    --------------------------
    A normal function returns once. An async generator uses 'yield' to
    produce values one at a time, pausing between each yield.

    EventSourceResponse calls this generator and pushes each yielded
    string to the browser as an SSE event data payload.

    HOW astream_events works:
    -------------------------
    agent_graph.astream_events() runs the graph and fires callback events
    as things happen. Each event is a dict:
        {
            "event": "on_chat_model_stream",   # what happened
            "name":  "ChatOpenAI",             # which component
            "data":  {"chunk": AIMessageChunk} # the actual data
        }

    We map LangGraph event names to our own SSE event types so the frontend
    has a clean, stable API that doesn't expose LangGraph internals.
    """
    try:
        # Build the message history: previous turns + new user message
        history = conversation_store[conversation_id]
        new_message = HumanMessage(content=user_message)
        messages_to_send = history + [new_message]

        # Accumulate the full agent response so we can store it after streaming
        full_response_messages = []

        # astream_events runs the graph asynchronously and yields events.
        # version="v2" is the current stable event schema from LangGraph.
        async for event in agent_graph.astream_events(
            {"messages": messages_to_send},
            version="v2",
        ):
            event_type = event.get("event")
            event_name = event.get("name", "")
            event_data = event.get("data", {})

            # ── Token streaming ───────────────────────────────────────────────
            # on_chat_model_stream fires for every token GPT-4o produces.
            # We only want tokens from the agent node (not tool calls formatting).
            # chunk.content is the actual token text — could be a word, part of
            # a word, or punctuation depending on how the model tokenizes.
            if event_type == "on_chat_model_stream":
                chunk = event_data.get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    # Only stream plain text tokens, not tool call tokens
                    # (tool call chunks have .tool_call_chunks, not .content)
                    if not getattr(chunk, "tool_call_chunks", None):
                        yield _sse_event("token", chunk.content)

            # ── Tool call started ─────────────────────────────────────────────
            # on_tool_start fires when the tools node begins executing a tool.
            # event_name is the tool name (e.g. "get_pod_status").
            # input contains the arguments GPT-4o passed to the tool.
            elif event_type == "on_tool_start":
                yield _sse_event("tool_call", {
                    "name": event_name,
                    "input": event_data.get("input", {}),
                })

            # ── Tool call finished ────────────────────────────────────────────
            # on_tool_end fires when the tool function has returned.
            # output is the string the tool returned (what the LLM will read).
            elif event_type == "on_tool_end":
                output = event_data.get("output")
                # ToolMessage output can be a string or an object with .content
                result_text = (
                    output.content if hasattr(output, "content") else str(output)
                )
                yield _sse_event("tool_result", {
                    "name": event_name,
                    "result": result_text,
                })

            # ── Graph finished ────────────────────────────────────────────────
            # on_chain_end with name "__end__" fires when the graph loop exits.
            # At this point we have the final state with all messages.
            elif event_type == "on_chain_end" and event_name == "LangGraph":
                output = event_data.get("output", {})
                full_response_messages = output.get("messages", [])

        # Store updated conversation history for the next turn.
        # We store: previous history + user message + all agent messages
        conversation_store[conversation_id] = list(messages_to_send) + list(full_response_messages)

        # Signal to the browser that streaming is complete.
        # The frontend uses this to stop the "typing..." indicator.
        yield _sse_event("done", {})

    except Exception as e:
        # Surface errors to the browser so the UI can show a useful message
        # rather than silently hanging or showing a blank response.
        yield _sse_event("error", {
            "message": str(e),
            "detail": traceback.format_exc(),
        })


# ── SSE event formatter ───────────────────────────────────────────────────────

def _sse_event(event_type: str, data: object) -> str:
    """
    Format a payload as an SSE event string.

    HOW SSE wire format works:
    --------------------------
    The SSE spec defines a simple text format over HTTP:

        data: {"type": "token", "data": "Why"}\\n\\n

    Each event is a line starting with "data: " followed by the payload,
    terminated by a blank line (\\n\\n).

    We put the event type inside the JSON payload (not as a separate SSE
    "event:" field) so the frontend can parse it in one place with JSON.parse().

    sse_starlette expects us to return just the data string — it adds the
    "data: " prefix and "\\n\\n" terminator automatically.
    """
    payload = json.dumps({"type": event_type, "data": data})
    return payload
