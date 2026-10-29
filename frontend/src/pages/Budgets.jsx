import { useEffect, useState } from "react";
import { api, inr } from "../api";

const STATE_COLOR = { over: "#C2410C", near: "#B45309", ok: "#0E7C66" };

export default function Budgets() {
  const [rows, setRows] = useState([]);
  const [cat, setCat] = useState("Food & Dining");
  const [limit, setLimit] = useState("");

  const load = () => api.budgets().then(setRows).catch(() => {});
  useEffect(() => { load(); }, []);

  const add = async () => {
    if (!limit) return;
    await api.setBudget(cat, Number(limit));
    setLimit(""); load();
  };

  return (
    <>
      <h1 className="grotesk" style={{ fontSize: 26, margin: "0 0 20px" }}>Budgets</h1>

      <div className="card" style={{ padding: 18, marginBottom: 20, display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <input className="input" value={cat} onChange={(e) => setCat(e.target.value)} style={{ maxWidth: 220 }} placeholder="Category" />
        <input className="input" value={limit} onChange={(e) => setLimit(e.target.value)} style={{ maxWidth: 160 }} placeholder="Monthly limit ₹" />
        <button className="btn" onClick={add}>Set budget</button>
      </div>

      <div className="card" style={{ padding: "8px 26px" }}>
        {rows.map((b, i) => (
          <div key={i} style={{ padding: "18px 0", borderTop: i ? "1px solid #f2f1ec" : "none" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 9, fontSize: 14, fontWeight: 600 }}>
              <span>{b.category}</span>
              <span className="num" style={{ color: STATE_COLOR[b.state] }}>{inr(b.used)} / {inr(b.limit)}</span>
            </div>
            <div style={{ height: 9, background: "#f0efea", borderRadius: 5, overflow: "hidden" }}>
              <div style={{ width: Math.min(100, b.pct) + "%", height: "100%", background: STATE_COLOR[b.state], borderRadius: 5 }} />
            </div>
            <div style={{ fontSize: 12, color: STATE_COLOR[b.state], marginTop: 7 }}>
              {b.state === "over" ? `Over by ${inr(b.used - b.limit)}` : `${inr(b.limit - b.used)} left`} · {b.pct}%
            </div>
          </div>
        ))}
        {!rows.length && <div style={{ padding: "18px 0", color: "var(--faint)" }}>No budgets set yet. Add one above.</div>}
      </div>
    </>
  );
}
