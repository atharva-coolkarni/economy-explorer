"""
Economy Explorer — agent evaluation.

Measures the one thing that matters most: for a given question, does the agent
fetch the RIGHT data series? Each case lists the question and the set of FRED
series ids that count as correct (some questions have more than one valid answer).

Run it with your backend's virtualenv active and your .env in place:

    python evaluate.py

It calls the real model + FRED for each case, so it makes live API calls and
takes a minute or two. Results can vary slightly run to run (the model isn't
perfectly deterministic) — that's expected.
"""

from app import run_agent  # reuse the exact agent the app uses

# (question, {acceptable FRED series ids})
CASES = [
    ("How fast are prices rising?",            {"CPIAUCSL", "CPILFESL"}),
    ("What is the inflation rate?",            {"CPIAUCSL", "CPILFESL"}),
    ("What is the unemployment rate?",         {"UNRATE"}),
    ("What are 30-year mortgage rates?",       {"MORTGAGE30US"}),
    ("What is the federal funds rate?",        {"FEDFUNDS", "DFF"}),
    ("What is the 10-year treasury yield?",    {"DGS10"}),
    ("How many jobs does the economy have?",   {"PAYEMS"}),
    ("How fast is the economy growing?",       {"GDPC1", "GDP", "A191RL1Q225SBEA"}),
    ("What is the labor force participation rate?", {"CIVPART"}),
    ("What is the personal saving rate?",      {"PSAVERT"}),
]


def fetched_ids(result):
    """The set of series ids the agent actually fetched for this question."""
    return {s["series_id"] for s in result.get("series", [])}


def run():
    passed = 0
    print(f"Running {len(CASES)} cases...\n")

    for question, acceptable in CASES:
        try:
            result = run_agent(question)
            got = fetched_ids(result)
            ok = bool(got & acceptable)  # did it fetch at least one acceptable series?
        except Exception as e:
            got, ok = {f"error: {e}"}, False

        passed += ok
        mark = "PASS" if ok else "FAIL"
        print(f"[{mark}] {question}")
        print(f"       expected one of {sorted(acceptable)}")
        print(f"       got           {sorted(got) or '—'}\n")

    pct = passed / len(CASES) * 100
    print(f"Score: {passed}/{len(CASES)} correct ({pct:.0f}%)")


if __name__ == "__main__":
    run()