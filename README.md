# Economy Explorer

**Ask the economy a plain question — get the official numbers, charted and explained.**

Economy Explorer turns a natural-language question like *"How fast are prices rising?"*
into a real chart and a plain-English explanation, grounded in official data from
[FRED](https://fred.stlouisfed.org/) (the U.S. Federal Reserve's database). An LLM
agent decides which data to pull, fetches it, and explains it — so an ordinary person
gets a clear answer instead of a spreadsheet.

**Live demo:** https://economy-explorer-1.onrender.com/
*(Hosted on a free tier — the first request after a quiet spell takes ~30–50s to wake up, then it's fast.)*

---

## What it does

Type a question (or tap an example) and the app:

1. Works out which economic series you mean (e.g. "inflation" → the Consumer Price Index).
2. Fetches the real, current numbers and picks a sensible transformation
   (raw levels vs. percent-change-from-a-year-ago).
3. Draws the chart and writes a short, jargon-free explanation.
4. Shows its work — a step-by-step trace of how it found the answer.

Example questions: *"What is the unemployment rate?"*, *"What are mortgage rates doing?"*,
*"Compare inflation and wage growth."*

## How it works

The core is an **LLM agent with tool use**. The model isn't asked to *know* the numbers
(its memory is frozen and would be stale); it's given two tools and told to go *fetch*
them, then explain only what it actually retrieved.

```
Browser (React + Recharts)
      │  POST /ask { question }
      ▼
Flask backend  ───►  Open-source LLM (via Groq)
      │                     ▲   │
      │     tool results    │   │  tool calls: search_series / fetch_series
      ▼                     │   ▼
   FRED API  ───────────────┘  (loops until the model has the data)
      │
      ▼
returns { answer, series, trace }  ───►  charted + explained in the UI
```

The backend holds the API keys, satisfies CORS, and owns the agent loop, so the frontend
stays a thin, swappable view. Because the model is reached through an OpenAI-compatible
endpoint, the same code runs on Groq's free hosted open models **or** a fully local
Ollama model with only a config change.

## Tech stack

- **Backend:** Python, Flask, gunicorn, `openai` SDK (pointed at Groq), httpx
- **Frontend:** React, Vite, Recharts
- **Model:** open-source LLM — `openai/gpt-oss-120b` (recommended) or Llama 3.3 70B — served free via [Groq](https://groq.com/)
- **Data:** [FRED](https://fred.stlouisfed.org/) API
- **Hosting:** Render (backend web service + static frontend)

## Running locally

You'll need two free API keys: [FRED](https://fredaccount.stlouisfed.org/apikeys)
and [Groq](https://console.groq.com/keys) (no credit card for either).

**Backend** (terminal 1):

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # then paste your two keys into .env
python app.py               # serves on http://localhost:8000
```

**Frontend** (terminal 2):

```bash
cd frontend
npm install
npm run dev                 # serves on http://localhost:5173
```

Open http://localhost:5173 and ask a question.

## Environment variables

| Variable        | Used by  | Required | Description                                                            |
| --------------- | -------- | -------- | ---------------------------------------------------------------------- |
| `FRED_API_KEY`  | backend  | yes      | Free key from FRED                                                      |
| `LLM_API_KEY`   | backend  | yes      | Free key from Groq                                                      |
| `LLM_MODEL`     | backend  | no       | Model id. Defaults to `llama-3.3-70b-versatile`; `openai/gpt-oss-120b` is more reliable at tool calling |
| `LLM_BASE_URL`  | backend  | no       | OpenAI-compatible endpoint. Defaults to Groq; set to `http://localhost:11434/v1` for local Ollama |
| `VITE_API_URL`  | frontend | for prod | The backend's public URL (defaults to `http://localhost:8000` in dev)  |

## Project structure

```
economy-explorer/
├─ backend/
│  ├─ app.py            # Flask server + agent loop + FRED tools
│  ├─ requirements.txt
│  └─ .env              # your keys (git-ignored)
├─ frontend/
│  ├─ index.html
│  ├─ vite.config.js
│  └─ src/
│     ├─ main.jsx
│     ├─ App.jsx        # UI: question bar, animated trace, chart, answer
│     └─ styles.css
└─ README.md
```

## Design notes

- **Grounded, not guessed.** The system prompt forbids inventing numbers — the model may
  only report data returned by its tools, which keeps answers current and honest.
- **Two tools, mapped to two endpoints.** `search_series` finds the right series from a
  phrase; `fetch_series` pulls its data. The agent chains them on its own.
- **Swappable everything.** The model (Groq ↔ Ollama) and the data source are isolated
  behind the backend, so either can change without touching the UI.
- **Stateless.** Each question is a self-contained round trip — no database needed for v1.

## Roadmap

- **Evaluation set** — a fixed list of questions paired with the series the agent *should*
  pick, to measure selection accuracy.
- **Caching** — economic data barely changes day to day, so caching FRED responses would
  cut latency and stay well within rate limits.
- **India / global data** — swap or add the [World Bank](https://data.worldbank.org/) and
  [data.gov.in](https://data.gov.in/) sources to serve non-US economies.
- **Tool-call retry** — auto-retry the occasional malformed tool call instead of erroring.

## Notes

Explanations are generated by an LLM and may be imperfect. This is an educational tool for
understanding public data — **not financial advice**.
