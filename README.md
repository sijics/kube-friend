# kubefriend

An AI-powered DevOps assistant for Kubernetes. Ask questions in plain English — kubefriend investigates your cluster and explains what's wrong.

## Prerequisites

- Docker + Docker Compose
- A running Kubernetes cluster with a valid `~/.kube/config`
- An OpenAI API key (or IBM watsonx credentials)

## Quickstart

```bash
# 1. Copy the env template and fill in your keys
cp .env.example .env

# 2. Start everything
docker compose up --build

# 3. Open the UI
open http://localhost:5173
```

## Example questions

- "Why is my openrag-backend pod failing?"
- "Show me the logs for the payments pod in the prod namespace"
- "What's wrong with my frontend deployment?"

## Architecture

```
Browser (React) → FastAPI → LangGraph ReAct Agent → Kubernetes Tools → Cluster
```

- **Frontend**: React + Vite + TypeScript — streaming chat UI
- **Backend**: FastAPI + SSE — streams agent steps in real time
- **Agent**: LangGraph ReAct loop — LLM decides what to investigate
- **LLM**: OpenAI GPT-4o or IBM watsonx Granite (set `LLM_PROVIDER` in `.env`)

## Project structure

```
kubefriend/
├── backend/        Python FastAPI + LangGraph agent
├── frontend/       React + Vite chat UI
├── docker-compose.yml
└── .env.example    All configuration keys documented here
```
