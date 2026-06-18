import React, { useEffect, useRef, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
 
const EXAMPLES = [
  "How fast are prices rising?",
  "What is the unemployment rate?",
  "What are mortgage rates doing?",
  "Compare inflation and wage growth",
];
 
const LINE_COLORS = ["#E5604D", "#E8A33D"];
 
// Messages that cycle while the agent is working.
const WORKING = [
  "Reading your question",
  "Searching the data",
  "Pulling the numbers",
  "Making sense of it",
];
 
// Turn the backend's series (each with its own dates) into one array recharts
// can plot: [{ date, SERIES_A: 1.2, SERIES_B: 3.4 }, ...].
function mergeSeries(series) {
  const byDate = {};
  series.forEach((s) => {
    (s.observations || []).forEach((o) => {
      byDate[o.date] = byDate[o.date] || { date: o.date };
      byDate[o.date][s.series_id] = o.value;
    });
  });
  return Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date));
}
 
// Prettify a tool-call trace line into something a person can read.
function humanizeTrace(line) {
  if (line.startsWith("search_series")) {
    const m = line.match(/'query':\s*'([^']+)'/) || line.match(/query['"]?:\s*['"]([^'"]+)/);
    return `Searched for "${m ? m[1] : "data"}"`;
  }
  if (line.startsWith("fetch_series")) {
    const id = line.match(/'series_id':\s*'([^']+)'/);
    const pc1 = line.includes("pc1");
    return `Fetched ${id ? id[1] : "a series"}${pc1 ? " as year-over-year change" : ""}`;
  }
  return line;
}
 
export default function App() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [workIdx, setWorkIdx] = useState(0);
  const inputRef = useRef(null);
 
  // Cycle the "working" messages while loading.
  useEffect(() => {
    if (!loading) return;
    setWorkIdx(0);
    const t = setInterval(() => setWorkIdx((i) => (i + 1) % WORKING.length), 1100);
    return () => clearInterval(t);
  }, [loading]);
 
  async function ask(q) {
    const query = (q ?? question).trim();
    if (!query || loading) return;
    setQuestion(query);
    setLoading(true);
    setError("");
    setData(null);
    try {
      const res = await fetch(`${API}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: query }),
      });
      const json = await res.json();
      if (json.error) setError(json.error);
      else if (!json.series || json.series.length === 0)
        setError("I couldn't find data for that one. Try rewording it.");
      else setData(json);
    } catch {
      setError("Couldn't reach the server. Is the backend running on port 8000?");
    } finally {
      setLoading(false);
    }
  }
 
  const merged = data ? mergeSeries(data.series) : [];
  const twoAxes =
    data && data.series.length === 2 && data.series[0].units !== data.series[1].units;
 
  return (
    <div className="page">
      <header className="masthead">
        <span className="eyebrow">Economy Explorer</span>
        <h1 className="hero">
          Ask the economy<br />
          <span className="hero-accent">a plain question.</span>
        </h1>
        <p className="subhead">
          Real numbers from official data, charted and explained — no jargon,
          no spreadsheets.
        </p>
      </header>
 
      <section className="ask" aria-label="Ask a question">
        <div className="ask-bar">
          <input
            ref={inputRef}
            className="ask-input"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ask()}
            placeholder="e.g. How fast are prices rising?"
            aria-label="Your question"
          />
          <button className="ask-btn" onClick={() => ask()} disabled={loading}>
            {loading ? "Working…" : "Ask"}
          </button>
        </div>
        <div className="chips">
          {EXAMPLES.map((ex) => (
            <button key={ex} className="chip" onClick={() => ask(ex)} disabled={loading}>
              {ex}
            </button>
          ))}
        </div>
      </section>
 
      {loading && (
        <section className="working" aria-live="polite">
          <span className="working-dot" />
          <span className="working-text">{WORKING[workIdx]}…</span>
        </section>
      )}
 
      {error && !loading && (
        <section className="notice" role="alert">
          {error}
        </section>
      )}
 
      {data && !loading && (
        <section className="result" aria-label="Result">
          <ol className="trace" aria-label="How the answer was found">
            {data.trace.map((line, i) => (
              <li key={i} className="trace-row" style={{ animationDelay: `${i * 0.12}s` }}>
                {humanizeTrace(line)}
              </li>
            ))}
          </ol>
 
          <div
            className="chart-card"
            style={{ animationDelay: `${data.trace.length * 0.12 + 0.1}s` }}
          >
            <div className="chart-titles">
              {data.series.map((s, i) => (
                <span className="chart-title" key={s.series_id}>
                  <span className="swatch" style={{ background: LINE_COLORS[i] }} />
                  {s.title}
                </span>
              ))}
            </div>
            <div className="chart-box">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={merged} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
                  <CartesianGrid stroke="#E2D9C9" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(d) => String(d).slice(0, 4)}
                    minTickGap={40}
                    tick={{ fill: "#6E7B73", fontSize: 12 }}
                    stroke="#C9BFAE"
                  />
                  <YAxis
                    yAxisId="left"
                    tick={{ fill: "#6E7B73", fontSize: 12 }}
                    stroke="#C9BFAE"
                    width={44}
                  />
                  {twoAxes && (
                    <YAxis
                      yAxisId="right"
                      orientation="right"
                      tick={{ fill: "#6E7B73", fontSize: 12 }}
                      stroke="#C9BFAE"
                      width={44}
                    />
                  )}
                  <Tooltip
                    contentStyle={{
                      background: "#15302A",
                      border: "none",
                      borderRadius: 10,
                      color: "#F7F3EC",
                      fontFamily: "JetBrains Mono, monospace",
                      fontSize: 12,
                    }}
                  />
                  {data.series.map((s, i) => (
                    <Line
                      key={s.series_id}
                      yAxisId={twoAxes && i === 1 ? "right" : "left"}
                      type="monotone"
                      dataKey={s.series_id}
                      stroke={LINE_COLORS[i]}
                      strokeWidth={2.5}
                      dot={false}
                      connectNulls
                      name={s.title}
                      isAnimationActive
                      animationDuration={900}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
 
          <blockquote
            className="answer"
            style={{ animationDelay: `${data.trace.length * 0.12 + 0.45}s` }}
          >
            {data.answer}
          </blockquote>
        </section>
      )}
 
      <footer className="foot">
        Data via FRED, the Federal Reserve's public database. Explanations are
        generated and may be imperfect — not financial advice.
      </footer>
    </div>
  );
}