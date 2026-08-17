import os
from langchain_core.language_models.chat_models import BaseChatModel


def get_llm() -> BaseChatModel:
    """
    Return a LangChain chat model based on the LLM_PROVIDER env var.

    WHY a factory function?
    -----------------------
    The rest of the codebase (graph.py, tests) calls get_llm() and gets back
    a standard LangChain BaseChatModel. It doesn't import OpenAI or watsonx
    directly — it doesn't even know which one it's talking to.

    This means:
    - Switching LLMs = change one line in .env
    - Testing = pass a mock that also implements BaseChatModel
    - Adding a new LLM = add one elif branch here, nothing else changes

    Supported providers (set LLM_PROVIDER in .env):
    - "openai"   → OpenAI GPT-4o  (default)
    - "watsonx"  → IBM watsonx Granite
    - "ollama"   → local Ollama (e.g. llama3, mistral)
    """
    provider = os.getenv("LLM_PROVIDER", "openai").lower().strip()

    if provider == "openai":
        return _build_openai()
    elif provider == "watsonx":
        return _build_watsonx()
    elif provider == "ollama":
        return _build_ollama()
    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER='{provider}'. "
            "Supported values: 'openai', 'watsonx', 'ollama'"
        )


def _build_openai() -> BaseChatModel:
    """
    Build a ChatOpenAI instance.

    HOW streaming works here:
    -------------------------
    We don't pass streaming=True explicitly — LangGraph's astream_events()
    handles streaming at the graph level by consuming the model's async
    generator. ChatOpenAI supports this natively through LangChain's
    standard streaming interface.

    Required env vars:
    - OPENAI_API_KEY  → your OpenAI secret key (sk-...)
    - OPENAI_MODEL    → which model to use, default "gpt-4o"
    """
    from langchain_openai import ChatOpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY is not set. "
            "Add it to your .env file."
        )

    model = os.getenv("OPENAI_MODEL", "gpt-4o")

    return ChatOpenAI(
        model=model,
        api_key=api_key,     # type: ignore[arg-type]
        temperature=0,       # 0 = deterministic, no creative guessing
                             # we want factual K8s analysis, not creative writing
    )


def _build_watsonx() -> BaseChatModel:
    """
    Build a ChatWatsonx instance.

    HOW watsonx auth works:
    -----------------------
    watsonx uses an API key + project ID (a workspace/org identifier).
    The URL points to your regional IBM Cloud watsonx endpoint.

    Required env vars:
    - WATSONX_API_KEY     → IBM Cloud API key
    - WATSONX_PROJECT_ID  → watsonx project ID (found in your project settings)
    - WATSONX_URL         → regional endpoint, e.g. https://us-south.ml.cloud.ibm.com
    - WATSONX_MODEL_ID    → model to use, e.g. ibm/granite-13b-chat-v2
    """
    from langchain_ibm import ChatWatsonx

    api_key = os.getenv("WATSONX_API_KEY")
    project_id = os.getenv("WATSONX_PROJECT_ID")
    url = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
    model_id = os.getenv("WATSONX_MODEL_ID", "ibm/granite-13b-chat-v2")

    if not api_key:
        raise ValueError("WATSONX_API_KEY is not set in .env")
    if not project_id:
        raise ValueError("WATSONX_PROJECT_ID is not set in .env")

    return ChatWatsonx(
        model_id=model_id,
        url=url,
        api_key=api_key,       # type: ignore[arg-type]
        project_id=project_id,
        params={
            "temperature": 0,  # same reasoning as OpenAI — deterministic answers
            "max_new_tokens": 1024,
        },
    )


def _build_ollama() -> BaseChatModel:
    """
    Build a ChatOllama instance for a locally-running Ollama server.

    Required env vars:
    - OLLAMA_MODEL    → model name, e.g. "llama3", "mistral" (default: "llama3")
    - OLLAMA_BASE_URL → Ollama server URL (default: http://localhost:11434)

    Install Ollama: https://ollama.com/
    Pull a model:  ollama pull llama3
    """
    from langchain_ollama import ChatOllama

    model = os.getenv("OLLAMA_MODEL", "llama3")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    return ChatOllama(
        model=model,
        base_url=base_url,
        temperature=0,
    )
