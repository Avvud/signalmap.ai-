# SignalMap AI

SignalMap AI is an AI research agent that investigates how a product/company is distributed across the public internet (website, YouTube, Reddit, GitHub), and produces an evidence-grounded research report.

## Tech Stack
- **Backend**: Python 3.11+, FastAPI, Pydantic v2
- **Job Queue**: Redis + Arq
- **Database**: SQLite (`aiosqlite`)
- **LLM Engine**: Groq API (OpenAI-compatible client)
- **Frontend**: React + Vite

---

## Local Setup (Phase 1)

### 1. Prerequisites
- Python 3.11+
- Redis running locally (`redis-server`) or a remote Redis URL (e.g. Upstash)

### 2. Environment Setup
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Unix/macOS:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

### 3. Running the Server & Worker

**Terminal 1: FastAPI Web Application**
```bash
uvicorn backend.main:app --reload --port 8000
```

**Terminal 2: Arq Background Worker**
```bash
arq backend.worker.WorkerSettings
```

---

## Known Limitations
- **No Auth**: Auth is explicitly out of scope for this MVP build. Rate limiting is enforced per IP via `slowapi`.
- **Text-Only**: Image/video processing is excluded to optimize token footprint and focus on core text positioning signals.
