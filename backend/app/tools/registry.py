"""
Tool registry — the single source of truth for all agent tools.

WHY a registry?
---------------
The LangGraph agent needs a list of tools to bind to the LLM via .bind_tools().
Rather than importing tools scattered across graph.py or main.py, everything
is collected here. Adding a new tool means:
  1. Create the tool file (e.g. tools/ingress.py)
  2. Import it here and add to TOOLS
  That's it — the agent picks it up automatically.
"""

from app.tools.pod_status import get_pod_status
from app.tools.pod_logs import get_pod_logs
from app.tools.pod_events import get_pod_events
from app.tools.deployment import get_deployment
from app.tools.pvc import get_pvc

# TOOLS is the complete list of tools the LLM agent can call.
# LangChain reads each tool's name, description (from docstring),
# and argument schema (from type hints) to build the tool-calling
# instructions it sends to GPT-4o.
TOOLS = [
    get_pod_status,
    get_pod_logs,
    get_pod_events,
    get_deployment,
    get_pvc,
]
