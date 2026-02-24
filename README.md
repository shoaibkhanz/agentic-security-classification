# Agentic Classification Tutorial

Hands-on tutorial project for building AI agents with `pydantic-ai`, from async fundamentals to a full capstone classification pipeline.

## What is in this repo

- `00_async_foundations.py` to `11_mlflow_observability.py`: step-by-step learning modules
- `capstone/`: multi-agent private securities classification pipeline
- `shared/`: shared models, fake data, and dependencies
- `web/`: FastAPI backend and Next.js frontend for interactive demo UI

## Prerequisites

- Python `3.13+`
- `uv` package manager

## Setup

```bash
uv sync
```

## Run Tutorial Modules

Run any module directly:

```bash
uv run python 00_async_foundations.py
uv run python 01_agents.py
uv run python 05b_mcp_tools.py
```

## Run the Capstone

```bash
uv run python -m capstone.run
```

Helpful extras:

```bash
uv run python -m capstone.evaluate
uv run python -m capstone.compare_models
uv run mlflow server --port 5000
```

If you run model comparisons across providers, set the API keys needed by the models you choose (for example `OPENAI_API_KEY` and/or `ANTHROPIC_API_KEY`).

## Run the Web Demo

Backend (from repo root):

```bash
uv run uvicorn web.api.main:app --reload --port 8000
```

Frontend (separate terminal):

```bash
cd web/frontend
npm install
npm run dev
```

Then open `http://localhost:3000`.

