import { useEffect, useState } from "react";
import { api, inr } from "../api";

export default function Subscriptions() {
  const [rows, setRows] = useState([]);
  useEffect(() => { api.recurring().then(setRows).catch(() => {}); }, []);

  const monthly = rows.filter((r) => !r.is_investment).reduce((s, r) => s + r.amount, 0);

  return (
    <>
      <h1 className="grotesk" style={{ fontSize: 26, margin: "0 0 4px" }}>Subscriptions & recurring</h1>
      <p style={{ color: "var(--faint)", margin: "0 0 20px", fontSize: 14 }}>Detected from repeating payments</p>

      <div className="card" style={{ padding: 18, marginBottom: 20, maxWidth: 260 }}>
        <div className="kpi-label">Monthly recurring (excl. investments)</div>
        <div className="kpi-value num">{inr(monthly)}</div>
      </div>

      <div className="card" style={{ overflow: "hidden" }}>
        {rows.map((r, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 16, padding: "16px 22px",
            borderTop: i ? "1px solid #f2f1ec" : "none" }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: 14.5 }}>{r.merchant}</div>
              <div style={{ fontSize: 12.5, color: "var(--faint)" }}>
                {r.category} · {r.cadence} · {r.occurrences}× · last {r.last_date}
              </div>
            </div>
            {r.is_investment && <span className="pill" style={{ background: "#ebf5ef", color: "var(--accent-dark)" }}>Wealth, not spend</span>}
            <div className="num" style={{ fontWeight: 600, minWidth: 90, textAlign: "right" }}>{inr(r.amount)}</div>
          </div>
        ))}
        {!rows.length && <div style={{ padding: 22, color: "var(--faint)" }}>No recurring payments detected yet.</div>}
      </div>
    </>
  );
}
