from typing import Any, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """
    The JSON body the browser sends to POST /api/chat.

    WHY Pydantic?
    -------------
    FastAPI uses Pydantic models to automatically:
    1. Parse and validate the incoming JSON body
    2. Return a clear 422 error if required fields are missing or wrong type
    3. Generate OpenAPI docs at /docs showing the expected schema

    Without Pydantic you'd manually parse request.json() and write your own
    validation. Pydantic does it in one class definition.
    """
    message: str = Field(..., description="The user's natural language question")
    conversation_id: str = Field(
        ...,
        description=(
            "A unique ID for this conversation session. "
            "Generate once (UUID) on page load and reuse for multi-turn context. "
            "The backend uses this to look up previous messages from this session."
        ),
    )


class ChatResponse(BaseModel):
    """
    The shape of a single SSE event payload.

    Each SSE event carries a 'type' and a 'data' field.
    The browser reads 'type' to know how to render 'data'.

    Event types:
    - "token"       : a single LLM output token (string) — append to current message
    - "tool_call"   : the LLM decided to call a tool — show in tool panel
    - "tool_result" : a tool finished running — update tool panel with result
    - "done"        : the agent loop has finished — close the stream
    - "error"       : something went wrong — show error in UI
    """
    type: str
    data: Any


# ── Dashboard schemas ─────────────────────────────────────────────────────────

class DashboardPod(BaseModel):
    name: str
    namespace: str
    status: str
    phase: str
    severity: str                   # "healthy" | "warning" | "critical"
    restarts: int
    age_hours: Optional[float]
    node: str
    diagnosis: Optional[str]        # AI-generated root cause (unhealthy pods only)
    suggestion: Optional[str]       # AI-generated fix suggestion


class DashboardSummary(BaseModel):
    total: int
    running: int
    warning: int
    critical: int


class DashboardResponse(BaseModel):
    pods: list[DashboardPod]
    summary: DashboardSummary
    namespaces: list[str]
    error: Optional[str] = None
