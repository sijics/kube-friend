from typing import Literal

from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode

from app.agent.state import AgentState
from app.agent.prompts import SYSTEM_PROMPT
from app.llm.factory import get_llm
from app.tools.registry import TOOLS


# ── Step 1: Bind the LLM to the tools ────────────────────────────────────────
#
# WHY .bind_tools()?
# ------------------
# GPT-4o doesn't know about our tools unless we tell it.
# .bind_tools(TOOLS) takes each tool's name, description, and argument schema
# and sends them to GPT-4o as part of every request in a special "tools" field.
# GPT-4o can then respond with a structured tool_call instead of plain text.
#
# Think of it as giving GPT-4o a menu of available actions.
# Without this, GPT-4o would just write text — it couldn't call get_pod_status.

_llm_with_tools = get_llm().bind_tools(TOOLS)


# ── Step 2: Define Node 1 — the "agent" node ─────────────────────────────────
#
# This is where the LLM thinks.
# Input:  the full message history (AgentState["messages"])
# Output: GPT-4o's reply — either an AIMessage with tool_calls OR plain text

def agent_node(state: AgentState) -> dict:
    """
    The thinking node. Sends the full conversation to GPT-4o and gets a reply.

    On the very first call, we prepend the system prompt so GPT-4o knows
    its role, rules, and available tools. On subsequent calls (after tool
    results), the system prompt is already in the message history.
    """
    messages = state["messages"]

    # Prepend system prompt if it's not already the first message.
    # This check prevents duplicating the system prompt on every loop iteration.
    if not messages or not isinstance(messages[0], SystemMessage):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)

    # Call GPT-4o with the full history.
    # The response is an AIMessage that contains either:
    # (a) .tool_calls = [{"name": "get_pod_status", "args": {...}}]  → go to tools node
    # (b) .content    = "Root cause is OOMKilled..."                 → go to END
    response = _llm_with_tools.invoke(messages)

    # Return a dict with the new message to append to state.
    # add_messages reducer (defined in state.py) appends this to the list.
    return {"messages": [response]}


# ── Step 3: Define Node 2 — the "tools" node ─────────────────────────────────
#
# WHY ToolNode instead of writing it ourselves?
# ---------------------------------------------
# ToolNode is LangGraph's built-in tool executor. It:
#   1. Reads the tool_calls from the last AIMessage
#   2. Finds the matching Python function in the TOOLS list by name
#   3. Calls it with the arguments GPT-4o provided
#   4. Wraps the return value in a ToolMessage
#   5. Returns {"messages": [ToolMessage(...)]} to be appended to state
#
# Without ToolNode, you'd write:
#   if tool_name == "get_pod_status": result = get_pod_status(...)
#   elif tool_name == "get_pod_logs": result = get_pod_logs(...)
#   ... one branch per tool
#
# ToolNode handles all of that automatically for any number of tools.

_tools_node = ToolNode(TOOLS)


# ── Step 4: Define the conditional edge — the routing logic ──────────────────
#
# After the agent node runs, we need to decide: continue looping or stop?
# This function reads the last message and returns the name of the next node.

def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    """
    Routing function: called after every agent node execution.

    Returns "tools"   → if GPT-4o made a tool call (keep looping)
    Returns "__end__" → if GPT-4o gave a plain text answer (we're done)

    WHY Literal["tools", "__end__"]?
    ----------------------------------
    This type hint tells LangGraph exactly which node names this function
    can return. LangGraph uses it to validate the graph at compile time.
    "__end__" is LangGraph's special sentinel for the END node.
    """
    last_message = state["messages"][-1]

    # AIMessage.tool_calls is a list of tool call requests.
    # If it's non-empty, GPT-4o wants to call a tool → route to tools node.
    # If it's empty, GPT-4o produced a final answer → stop the loop.
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    return END  # type: ignore[return-value]
    # END is LangGraph's constant for "__end__" — same thing, more readable


# ── Step 5: Build and compile the graph ──────────────────────────────────────
#
# Now we wire all pieces together.
# StateGraph(AgentState) creates a graph where every node receives and
# returns an AgentState (or a partial dict that gets merged into it).

def build_graph():
    builder = StateGraph(AgentState)

    # Register nodes — give each a string name and a callable
    builder.add_node("agent", agent_node)
    builder.add_node("tools", _tools_node)

    # Entry point: always start at the agent node
    builder.add_edge(START, "agent")

    # Conditional edge from agent node:
    # Call should_continue() to decide where to go next
    builder.add_conditional_edges("agent", should_continue)

    # Unconditional edge from tools node:
    # After running a tool, always go back to the agent node to think again
    builder.add_edge("tools", "agent")

    # compile() validates the graph (checks for unreachable nodes, type mismatches)
    # and returns a runnable object with .invoke(), .ainvoke(), .astream_events()
    return builder.compile()


# Module-level singleton — built once when the module is first imported.
# FastAPI will import this module at startup, building the graph once.
# All subsequent requests reuse the same compiled graph — no rebuild cost.
agent_graph = build_graph()
