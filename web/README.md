# Securities Classifier — Web UI

Full-stack showcase for the capstone private-securities classification pipeline.
FastAPI streams live SSE events from `pydantic-graph` while Next.js renders an
interactive classification experience with confidence tracking, reasoning chains,
and a feedback loop.

A Python-only Streamlit frontend is also available in `../streamlit_ui`.

## Architecture

```
web/
├── api/                    FastAPI backend
│   ├── main.py             App entry point + lifespan
│   ├── routes.py           REST + SSE endpoints
│   ├── streaming.py        graph.iter() → SSE events
│   ├── memory.py           JSON file persistence
│   └── schemas.py          Request/response models
│
└── frontend/               Next.js 16 app (App Router)
    └── src/
        ├── app/            Pages (/, /history)
        ├── components/     UI components + shadcn primitives
        ├── hooks/          useClassification (SSE), useHistory
        ├── lib/            Types, API client, constants
        └── providers/      Theme provider (light/dark/grey)
```

## Quick Start

```bash
# Terminal 1 — FastAPI backend (from project root)
uv run uvicorn web.api.main:app --reload --port 8000

# Terminal 2 — Next.js frontend
cd web/frontend && npm run dev
```

Open **http://localhost:3000**

The frontend proxies `/api/*` to the backend via `next.config.ts` rewrites, so
no CORS issues arise.

### Streamlit Frontend Alternative

```bash
# Terminal 1 — FastAPI backend
uv run uvicorn web.api.main:app --reload --port 8000

# Terminal 2 — Streamlit frontend (from project root)
CLASSIFIER_API_BASE_URL=http://localhost:8000 uv run streamlit run streamlit_ui/app.py
```

Open **http://localhost:8501**

## Features

- **Live streaming** — SSE events per graph node (activity feed + confidence chart)
- **Confidence tracking** — Animated Recharts line chart with threshold reference
- **Reasoning chain** — Expandable accordion showing step-by-step evidence
- **Evidence panel** — Tabbed view grouped by source type
- **Feedback loop** — "Got this wrong?" opens a sheet for free-text corrections
  with optional category override and automatic rerun
- **History** — Persistent classification records with correction tracking
- **3 themes** — Light, Dark, Grey (Bloomberg-terminal aesthetic)
- **Keyboard shortcuts** — Cmd+Enter to classify

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/classify` | SSE stream of classification events |
| POST | `/api/feedback/{id}` | Submit correction, optionally rerun |
| GET | `/api/history` | List all classifications |
| GET | `/api/history/{id}` | Single record with corrections |
| DELETE | `/api/history/{id}` | Delete a record |
| GET | `/api/examples` | Example securities for UI cards |
| GET | `/api/health` | Health check |

## Tech Stack

**Backend**: FastAPI, sse-starlette, pydantic-graph
**Frontend**: Next.js 16, React, TypeScript, Tailwind CSS v4, shadcn/ui, Recharts, Framer Motion
**Streaming**: `@microsoft/fetch-event-source` (POST-based SSE)
