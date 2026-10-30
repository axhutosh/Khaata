import { useEffect, useState } from "react";
import { api, inr } from "../api";
import { CAT_COLORS, CategoryDot } from "../categories.jsx";

const CATEGORIES = Object.keys(CAT_COLORS);

export default function Transactions() {
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState("");
  const [onlyUncat, setOnlyUncat] = useState(false);
  const [saving, setSaving] = useState(null);
  const [rerun, setRerun] = useState(null); // null | "busy" | number changed

  const load = () => api.transactions({ ...(q ? { q } : {}), ...(onlyUncat ? { category: "Uncategorised" } : {}) })
    .then(setRows).catch(() => {});
  useEffect(() => { load(); }, [onlyUncat]);

  // a change applies to every payment to this merchant and is remembered for future uploads
  const recategorize = async (r, category) => {
    setSaving(r.id);
    try { await api.recategorize(r.id, category); await load(); } finally { setSaving(null); }
  };

  const reclassify = async () => {
    setRerun("busy");
    try { const r = await api.reclassify(); setRerun(r.changed); await load(); } catch { setRerun(null); }
  };

  return (
    <>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
        <h1 className="grotesk" style={{ fontSize: 26, margin: 0, marginRight: "auto" }}>Transactions</h1>
        {typeof rerun === "number" && (
          <span role="status" style={{ fontSize: 13, color: "var(--accent-dark)" }}>
            ✓ {rerun ? `Updated ${rerun} transaction${rerun > 1 ? "s" : ""}` : "Already up to date"}
          </span>
        )}
        <button className="btn btn-ghost" onClick={reclassify} disabled={rerun === "busy"} style={{ fontSize: 13.5, padding: "9px 14px" }}
          title="Re-run person/merchant detection and categories on saved rows. Your own corrections are kept.">
          {rerun === "busy" ? "Re-checking…" : "Re-run auto-categorise"}
        </button>
      </div>
      <form onSubmit={(e) => { e.preventDefault(); load(); }}
        style={{ display: "flex", gap: 10, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
        <input className="input" placeholder="Search merchant or narration" value={q}
          onChange={(e) => setQ(e.target.value)} style={{ maxWidth: 320 }} aria-label="Search transactions" />
        <button className="btn btn-ghost" type="submit">Search</button>
        <label style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 14, color: "var(--muted)", cursor: "pointer", marginLeft: 6 }}>
          <input type="checkbox" checked={onlyUncat} onChange={(e) => setOnlyUncat(e.target.checked)} />
          Only uncategorised
        </label>
      </form>
      <p style={{ fontSize: 13, color: "var(--faint)", margin: "0 0 12px" }}>
        Changing a category updates every payment to that merchant and is remembered for future uploads.
      </p>
      <div className="card" style={{ overflow: "auto" }}>
        <table>
          <thead><tr><th>Date</th><th>Merchant</th><th>Category</th><th style={{ textAlign: "right" }}>Amount</th></tr></thead>
          <tbody>
            {rows.map((r) => {
              const needs = r.category === "Uncategorised";
              return (
                <tr key={r.id}>
                  <td className="num" style={{ color: "var(--muted)", whiteSpace: "nowrap" }}>{r.date}</td>
                  <td>
                    <div style={{ fontWeight: 600, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                      {r.merchant}
                      {r.kind === "person" && <span className="pill" style={{ background: "#eef0f4", color: "var(--muted)" }}>Person</span>}
                    </div>
                    <div style={{ fontSize: 11.5, color: "#a9adb4", fontFamily: "Space Grotesk", wordBreak: "break-all" }}>{r.raw.slice(0, 60)}</div>
                  </td>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <CategoryDot category={r.category} />
                      <select className="input" value={r.category} disabled={saving === r.id}
                        onChange={(e) => recategorize(r, e.target.value)} aria-label={`Category for ${r.merchant}`}
                        style={{ padding: "7px 10px", fontSize: 13.5, minWidth: 170,
                          ...(needs ? { background: "#fdf3e7", borderColor: "#e4c48f", color: "#92600f", fontWeight: 600 } : {}) }}>
                        {[...new Set([...CATEGORIES, r.category])].map((c) => <option key={c}>{c}</option>)}
                      </select>
                    </div>
                  </td>
                  <td className="num" style={{ textAlign: "right", fontWeight: 600, whiteSpace: "nowrap", color: r.type === "credit" ? "var(--accent)" : "var(--ink)" }}>
                    {r.type === "credit" ? "+" : "−"}{inr(r.amount)}
                  </td>
                </tr>
              );
            })}
            {!rows.length && <tr><td colSpan={4} style={{ color: "var(--faint)" }}>No transactions match.</td></tr>}
          </tbody>
        </table>
      </div>
    </>
  );
}
