import { useEffect, useState } from "react";
import { api, inr } from "../api";

export default function Transactions() {
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState("");

  const load = () => api.transactions(q ? { q } : {}).then(setRows).catch(() => {});
  useEffect(() => { load(); }, []);

  return (
    <>
      <h1 className="grotesk" style={{ fontSize: 26, margin: "0 0 16px" }}>Transactions</h1>
      <div style={{ display: "flex", gap: 10, marginBottom: 16 }}>
        <input className="input" placeholder="Search merchant or narration" value={q}
          onChange={(e) => setQ(e.target.value)} style={{ maxWidth: 320 }} />
        <button className="btn btn-ghost" onClick={load}>Search</button>
      </div>
      <div className="card" style={{ overflow: "hidden" }}>
        <table>
          <thead><tr><th>Date</th><th>Merchant</th><th>Category</th><th style={{ textAlign: "right" }}>Amount</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td className="num" style={{ color: "var(--muted)", whiteSpace: "nowrap" }}>{r.date}</td>
                <td>
                  <div style={{ fontWeight: 600 }}>{r.merchant}</div>
                  <div style={{ fontSize: 11.5, color: "#a9adb4", fontFamily: "Space Grotesk" }}>{r.raw.slice(0, 48)}</div>
                </td>
                <td><span className="pill" style={{ background: "#f0efea", color: "var(--muted)" }}>{r.category}</span></td>
                <td className="num" style={{ textAlign: "right", fontWeight: 600, color: r.type === "credit" ? "var(--accent)" : "var(--ink)" }}>
                  {r.type === "credit" ? "+" : "−"}{inr(r.amount)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
