# AGENTS.md

## Cursor Cloud specific instructions

### Project Overview
Agent for Exam — AI-powered exam assistant (FastAPI backend + Vue 3 frontend + vendored LightRAG library). All storage is file-based (no external database needed).

### Services

| Service | Command | Port |
|---------|---------|------|
| Backend (FastAPI) | `cd backend && source venv/bin/activate && PYTHONPATH=/workspace/LightRAG:$PYTHONPATH uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` | 8000 |
| Frontend (Vite) | `cd frontend && npm run dev -- --host 0.0.0.0` | 5173 |

### Key Caveats
- **LightRAG PYTHONPATH**: The backend imports `lightrag` from the vendored `/workspace/LightRAG` directory via `sys.path` injection. When running uvicorn directly, set `PYTHONPATH=/workspace/LightRAG:$PYTHONPATH` to ensure imports resolve.
- **Backend .env**: Must exist at `backend/.env` (copy from `backend/.env.example`). LLM API keys are configured via the frontend Settings UI at runtime, but the `.env` file must exist for the app to start.
- **python3.12-venv**: The system package `python3.12-venv` is required to create the virtualenv. The update script handles this.
- **No ESLint / dedicated lint**: The project has no dedicated lint configuration for the main backend or frontend. The vendored LightRAG has a `.pre-commit-config.yaml` with ruff but that's specific to the LightRAG fork.
- **Tests**: `pytest` runs from `backend/` with `PYTHONPATH` including LightRAG. Currently only fixtures exist (no test functions), so `pytest` exits with code 5 (no tests collected) — this is expected.
- **Data directories**: `backend/uploads/`, `backend/data/`, and `backend/logs/` are created at runtime. If they don't exist, the app creates them automatically.
- **Frontend proxy**: Vite proxies `/api` to `http://localhost:8000`. Backend must be running for API calls to work.
- **External API dependency**: Full LLM features (chat, KG extraction, mindmap) require a SiliconFlow API key. The app starts without it, but chat responses will show API key errors.
- **Programmatic API key config**: If the `SILICONFLOW_API_KEY` env var is available, configure all four scenes (knowledge_graph, chat, mindmap, embedding) via POST to `/api/settings/llm-config/{scene}` with `binding: "siliconflow"` and the API key. This is equivalent to configuring via the frontend Settings UI (⚙️).
- **siliconcloud vs siliconflow**: These are the same provider. The LightRAG library uses `siliconcloud`; the app uses `siliconflow`. The API normalizes `siliconcloud` → `siliconflow` automatically.
