import { useEffect, useState } from "react";
import { api, inr, monthLabel } from "../api";

const STATE_COLOR = { over: "#C2410C", near: "#B45309", ok: "#0E7C66" };
const STATE_TEXT = { over: "Over", near: "Near limit", ok: "On track" };

function Bar({ used, limit, projected, state }) {
  const pct = (n) => Math.min(100, limit ? (n / limit) * 100 : 0) + "%";
  return (
    <div style={{ position: "relative", height: 9, background: "#f0efea", borderRadius: 5 }}>
      <div style={{ width: pct(used), height: "100%", background: STATE_COLOR[state], borderRadius: 5 }} />
      {projected > used && (
        <div title="Month-end projection" style={{ position: "absolute", top: -3, bottom: -3, left: pct(projected),
          width: 2, background: "var(--ink)", opacity: 0.55 }} />
      )}
    </div>
  );
}

function Status({ b }) {
  const color = STATE_COLOR[b.state];
  return (
    <div style={{ fontSize: 12, color, marginTop: 7 }}>
      <b>{STATE_TEXT[b.state]}</b> · {b.state === "over" ? `over by ${inr(b.used - b.limit)}` : `${inr(b.limit - b.used)} left`}
      {b.projected > b.used && <span style={{ color: "var(--muted)" }}> · projected {inr(b.projected)} by month-end</span>}
    </div>
  );
}

export default function Budgets() {
  const [data, setData] = useState(null);
  const [cat, setCat] = useState("Food & Dining");
  const [limit, setLimit] = useState("");

  const load = () => api.budgets().then(setData).catch(() => {});
  useEffect(() => { load(); }, []);

  const add = async () => {
    if (!limit) return;
    await api.setBudget(cat, Number(limit));
    setLimit(""); load();
  };

  const rows = data?.items ?? [];
  const overall = data?.overall;

  return (
    <>
      <h1 className="grotesk" style={{ fontSize: 26, margin: "0 0 4px" }}>Budgets</h1>
      {data && <p style={{ color: "var(--muted)", margin: "0 0 20px", fontSize: 14 }}>{monthLabel(data.month)} · latest month in your statements</p>}

      <div className="card" style={{ padding: 18, marginBottom: 20, display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <input className="input" value={cat} onChange={(e) => setCat(e.target.value)} style={{ maxWidth: 220 }} placeholder="Category" />
        <input className="input" value={limit} onChange={(e) => setLimit(e.target.value)} style={{ maxWidth: 160 }} placeholder="Monthly limit ₹" />
        <button className="btn" onClick={add}>Set budget</button>
      </div>

      {overall && rows.length > 0 && (
        <div className="card" style={{ padding: "20px 26px", marginBottom: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 10, alignItems: "baseline" }}>
            <span style={{ fontWeight: 600 }}>Overall</span>
            <span className="num grotesk" style={{ fontSize: 20, fontWeight: 600, color: STATE_COLOR[overall.state] }}>
              {inr(overall.used)} <span style={{ color: "var(--faint)", fontSize: 15 }}>/ {inr(overall.limit)}</span>
            </span>
          </div>
          <Bar {...overall} />
          <Status b={overall} />
        </div>
      )}

      <div className="card" style={{ padding: "8px 26px" }}>
        {rows.map((b, i) => (
          <div key={b.category} style={{ padding: "18px 0", borderTop: i ? "1px solid #f2f1ec" : "none" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 9, fontSize: 14, fontWeight: 600 }}>
              <span>{b.category}</span>
              <span className="num" style={{ color: STATE_COLOR[b.state] }}>{inr(b.used)} / {inr(b.limit)} · {b.pct}%</span>
            </div>
            <Bar {...b} />
            <Status b={b} />
          </div>
        ))}
        {!rows.length && <div style={{ padding: "18px 0", color: "var(--faint)" }}>No budgets set yet. Add one above.</div>}
      </div>
    </>
  );
}
