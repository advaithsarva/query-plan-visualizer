import { useState } from "react";
import PlanTree from "./PlanTree";

const DEFAULT_SQL = "SELECT * FROM orders WHERE customer_id = 42;";

export default function App() {
  const [sql, setSql] = useState(DEFAULT_SQL);
  const [plan, setPlan] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [execTime, setExecTime] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleRun() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/explain", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: sql }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "request failed");
      setPlan(data.plan);
      setSuggestions(data.suggestions);
      setExecTime(data.execution_time_ms);
    } catch (e) {
      setError(e.message);
      setPlan(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="shell">
      <div className="chrome">
        <div className="chrome-bar">
          <span className="dot red" />
          <span className="dot amber" />
          <span className="dot green" />
          <span className="chrome-title">postgres — explain analyze — 127.0.0.1:5432</span>
        </div>
        <div className="chrome-body">
          <h1 className="mast">
            <span className="prompt">&gt;</span> query_plan_visualizer<span className="cursor">&nbsp;</span>
          </h1>
          <p className="subtitle">paste a SELECT, run it, watch where postgres actually spends its time.</p>

          <label className="field-label" htmlFor="sql-input">query</label>
          <textarea
            id="sql-input"
            value={sql}
            onChange={(e) => setSql(e.target.value)}
            spellCheck={false}
          />

          <div className="controls">
            <button className="run" onClick={handleRun} disabled={loading}>
              {loading ? "running…" : "▶ run explain analyze"}
            </button>
            {execTime != null && (
              <span className="exec-time">
                exec time: <strong>{execTime.toFixed(2)} ms</strong>
              </span>
            )}
          </div>

          {error && <div className="error-banner">{error}</div>}

          {plan && (
            <div className="results-grid">
              <div className="hud-panel">
                <span className="corner tl" />
                <span className="corner tr" />
                <span className="corner bl" />
                <span className="corner br" />
                <h2 className="panel-heading">
                  execution <span className="lit">tree</span>
                </h2>
                <PlanTree data={plan} />
              </div>

              <div className="hud-panel">
                <span className="corner tl" />
                <span className="corner tr" />
                <span className="corner bl" />
                <span className="corner br" />
                <h2 className="panel-heading">
                  rewrite <span className="lit">suggestions</span>
                </h2>
                {suggestions.length === 0 ? (
                  <p style={{ color: "var(--fg-dim)", fontSize: 12.5 }}>no issues flagged.</p>
                ) : (
                  suggestions.map((s, i) => (
                    <div className="suggestion-item" key={i}>
                      <span className="flag">▲</span>
                      <span>{s}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

          {!plan && !error && (
            <div className="empty-state">no plan loaded — run a query to see its execution tree</div>
          )}
        </div>
      </div>
    </div>
  );
}
