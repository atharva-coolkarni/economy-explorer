"""
Economy Explorer backend - increment 3b: the agent loop.

The model can now USE the search/fetch functions as "tools". For a question it:
  1. calls search_series to find the right series,
  2. calls fetch_series to get the real data (picking pc1 for inflation/growth),
  3. writes a plain-language answer grounded in the numbers it fetched.

We also return `series` (the data it pulled) and `trace` (what it did) so the
frontend can chart the result and show its work.

Run:   python app.py
Test:  http://localhost:8000/ask?q=what is the current US unemployment rate
       http://localhost:8000/ask?q=how fast are prices rising
"""

import json
import os

import httpx
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from openai import OpenAI

load_dotenv()

FRED_API_KEY = os.getenv("FRED_API_KEY", "")
FRED_BASE = "https://api.stlouisfed.org/fred"

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
llm = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY or "missing")

app = Flask(__name__)
CORS(app)  # let the React dev server (a different port) call this API


# ---------------------------------------------------------------------------
# The functions (unchanged from before) - these become the model's tools.
# ---------------------------------------------------------------------------

def search_series(query, limit=8):
    with httpx.Client(timeout=30) as http:
        r = http.get(
            f"{FRED_BASE}/series/search",
            params={
                "search_text": query,
                "api_key": FRED_API_KEY,
                "file_type": "json",
                "order_by": "popularity",
                "sort_order": "desc",
                "limit": limit,
            },
        )
        r.raise_for_status()
    return [
        {"series_id": s["id"], "title": s["title"],
         "frequency": s.get("frequency_short"), "units": s.get("units_short")}
        for s in r.json().get("seriess", [])
    ]


def fetch_series(series_id, units="lin", start="2015-01-01"):
    with httpx.Client(timeout=30) as http:
        meta = http.get(
            f"{FRED_BASE}/series",
            params={"series_id": series_id, "api_key": FRED_API_KEY, "file_type": "json"},
        )
        obs = http.get(
            f"{FRED_BASE}/series/observations",
            params={
                "series_id": series_id, "api_key": FRED_API_KEY, "file_type": "json",
                "units": units, "observation_start": start,
            },
        )
        meta.raise_for_status()
        obs.raise_for_status()
    title = meta.json()["seriess"][0]["title"]
    points = [
        {"date": o["date"], "value": float(o["value"])}
        for o in obs.json()["observations"] if o["value"] != "."
    ]
    return {"series_id": series_id, "title": title, "units": units, "observations": points}


# ---------------------------------------------------------------------------
# Describing those functions to the model, in the format it expects.
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_series",
            "description": "Search FRED for an economic data series by a plain phrase. "
                           "Returns candidate series with their ids and titles.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string",
                              "description": "What to search for, e.g. 'inflation'."}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_series",
            "description": "Fetch the data points for one FRED series id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "series_id": {"type": "string", "description": "FRED id, e.g. 'CPIAUCSL'."},
                    "units": {
                        "type": "string",
                        "enum": ["lin", "pc1"],
                        "description": "lin = raw levels; pc1 = percent change from a year ago "
                                       "(use for inflation and growth-rate questions).",
                    },
                },
                "required": ["series_id"],
            },
        },
    },
]

SYSTEM_PROMPT = (
    "You are Economy Explorer, explaining the economy to everyday people in plain language.\n"
    "For each question: first use search_series to find the right series, then use "
    "fetch_series to get its data (choose pc1 for inflation or growth-rate questions, "
    "lin otherwise). Finally, answer in 2-3 short sentences using the real numbers you "
    "fetched. Never invent numbers - only use data you actually fetched. "
    "This is information, not financial advice."
)


def call_tool(name, args):
    """Run a requested tool. Returns (result_for_model, full_data_or_None)."""
    if name == "search_series":
        return search_series(args["query"]), None
    if name == "fetch_series":
        data = fetch_series(args["series_id"], args.get("units", "lin"))
        # Give the model a small summary; keep the full series for the frontend.
        obs = data["observations"]
        summary = {"series_id": data["series_id"], "title": data["title"],
                   "units": data["units"], "count": len(obs),
                   "latest": obs[-1] if obs else None}
        return summary, data
    return {"error": f"unknown tool {name}"}, None


def run_agent(question):
    """The loop: keep calling the model, running any tools it asks for, until
    it stops asking for tools and returns a final answer."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    collected, trace = [], []

    for _ in range(6):  # cap the rounds so a confused model can't loop forever
        resp = llm.chat.completions.create(
            model=LLM_MODEL, messages=messages, tools=TOOLS,
            tool_choice="auto", temperature=0.2, max_tokens=700,
        )
        msg = resp.choices[0].message

        # No tool requested -> this is the final answer.
        if not msg.tool_calls:
            return {"answer": msg.content, "series": collected, "trace": trace}

        # Record the model's "please call these tools" turn...
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ],
        })
        # ...then run each tool and feed the result back as a "tool" message.
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
                result, data = call_tool(tc.function.name, args)
                if data:
                    collected.append(data)
                trace.append(f"{tc.function.name}({args})")
            except Exception as e:
                result = {"error": str(e)}
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})

    return {"answer": "(Stopped after too many steps.)", "series": collected, "trace": trace}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return jsonify({"ok": True, "have_fred_key": bool(FRED_API_KEY),
                    "have_llm_key": bool(LLM_API_KEY)})


@app.route("/ask", methods=["GET", "POST"])
def ask():
    """Ask a question; the model uses tools to fetch real data and explains it."""
    if request.method == "POST":
        question = (request.get_json(silent=True) or {}).get("question", "").strip()
    else:
        question = request.args.get("q", "").strip()
    if not LLM_API_KEY or not FRED_API_KEY:
        return jsonify({"error": "Set both FRED_API_KEY and LLM_API_KEY in backend/.env."}), 400
    if not question:
        return jsonify({"error": "Add a question, e.g. /ask?q=how fast are prices rising"}), 400
    try:
        return jsonify(run_agent(question))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Kept as handy debugging endpoints.
@app.get("/search")
def search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "Add a phrase, e.g. /search?q=inflation"}), 400
    try:
        return jsonify({"query": query, "results": search_series(query)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.get("/series/<series_id>")
def series(series_id):
    try:
        return jsonify(fetch_series(series_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(port=8000, debug=True)