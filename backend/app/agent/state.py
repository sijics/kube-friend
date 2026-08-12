from typing import Annotated
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    The entire memory of the agent at any point in the loop.

    WHY just a list of messages?
    ----------------------------
    Every interaction between the user, the LLM, and tools is represented
    as a message. The full message history IS the agent's context — GPT-4o
    reads the entire list on every loop iteration to decide what to do next.

    Message types used in this agent:
    - SystemMessage   : the system prompt (instructions, personality) — added once at the start
    - HumanMessage    : the user's question
    - AIMessage       : GPT-4o's reply — either a tool call or a final answer
    - ToolMessage     : the result returned by a tool after it ran

    A full conversation looks like:
        SystemMessage("You are a K8s expert...")
        HumanMessage("Why is my pod failing?")
        AIMessage(tool_calls=[{name: "get_pod_status", args: {...}}])
        ToolMessage("Pod phase: Running, Restarts: 14, Last: OOMKilled")
        AIMessage(tool_calls=[{name: "get_pod_logs", args: {...}}])
        ToolMessage("FATAL: Killed process — out of memory")
        AIMessage("Root cause: memory limit too low. Fix: increase limits.memory to 1Gi")

    WHY Annotated[list, add_messages]?
    -----------------------------------
    When a node returns {"messages": [new_message]}, LangGraph needs to know
    whether to REPLACE the list or APPEND to it.

    add_messages is a reducer that says: APPEND.

    Without it, every node return would wipe out the previous messages.
    With it, the list grows naturally as the conversation progresses.
    """
    messages: Annotated[list[BaseMessage], add_messages]
