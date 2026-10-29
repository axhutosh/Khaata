import { useMemo, useState } from "react";
import { inr, inrExact } from "../api";

const AMBER = { bg: "#fdf3e7", line: "#f0e2c9", ink: "#92600f" };
const JADE = { bg: "#ecf6f1", line: "#cde7db", ink: "#0a5f4e" };

// The trust step: nothing is saved until "Looks good — save".
export default function Review({ preview, busy, onSave, onCancel }) {
  const { rows, balance_check: bc, categories } = preview;
  const [corrections, setCorrections] = useState({}); // merchant -> category
  const [onlyFlagged, setOnlyFlagged] = useState(false);

  const categoryOf = (r) => corrections[r.merchant] ?? r.category;
  const fresh = rows.filter((r) => !r.duplicate);
  const flagged = fresh.filter((r) => categoryOf(r) === "Uncategorised").length;
  const shown = useMemo(
    () => (onlyFlagged ? rows.filter((r) => !r.duplicate && categoryOf(r) === "Uncategorised") : rows),
    [rows, onlyFlagged, corrections],
  );

  const setCategory = (r, category) => {
    const next = { ...corrections };
    const original = rows.find((x) => x.merchant === r.merchant).category;
    if (category === original) delete next[r.merchant];
    else next[r.merchant] = category;
    setCorrections(next);
  };

  const ok = bc.reconciles;
  const tone = ok ? JADE : AMBER;

  return (
    <>
      <div style={{ background: tone.bg, border: `1px solid ${tone.line}`, color: tone.ink,
        borderRadius: 12, padding: "14px 18px", marginBottom: 18, fontSize: 14 }}>
        <b>{ok ? "✓ Balance check passed." : "⚠ Balance check needs a look."}</b>{" "}
        <span className="num">
          {inrExact(bc.opening)} + {inrExact(bc.credits)} − {inrExact(bc.debits)} = {inrExact(bc.expected_closing)}
        </span>
        {ok
          ? " — matches the statement's closing balance. Nothing missed."
          : <> — but the statement closes at <span className="num">{inrExact(bc.statement_closing)}</span>{" "}
              (off by <span className="num">{inrExact(bc.difference)}</span>). A row may have been mis-read.</>}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap", marginBottom: 14, fontSize: 14 }}>
        <span><b>{fresh.length}</b> new</span>
        {preview.duplicates > 0 && <span style={{ color: "var(--muted)" }}><b>{preview.duplicates}</b> already saved (skipped)</span>}
        <span style={{ color: flagged ? AMBER.ink : "var(--muted)" }}><b>{flagged}</b> need a category</span>
        {Object.keys(corrections).length > 0 && (
          <span style={{ color: "var(--accent-dark)" }}>
            <b>{Object.keys(corrections).length}</b> merchant{Object.keys(corrections).length > 1 ? "s" : ""} recategorised — Khaata will remember
          </span>
        )}
        <label style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 7, color: "var(--muted)", cursor: "pointer" }}>
          <input type="checkbox" checked={onlyFlagged} onChange={(e) => setOnlyFlagged(e.target.checked)} />
          Only show rows needing a category
        </label>
      </div>

      <div className="card" style={{ overflow: "auto", marginBottom: 18 }}>
        <table>
          <thead><tr><th>Date</th><th>Merchant</th><th>Category</th><th style={{ textAlign: "right" }}>Amount</th></tr></thead>
          <tbody>
            {shown.map((r, i) => {
              const cat = categoryOf(r);
              const needs = !r.duplicate && cat === "Uncategorised";
              return (
                <tr key={i} style={{ opacity: r.duplicate ? 0.5 : 1 }}>
                  <td className="num" style={{ color: "var(--muted)", whiteSpace: "nowrap" }}>{r.txn_date}</td>
                  <td>
                    <div style={{ fontWeight: 600, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                      {r.merchant}
                      {r.counterparty_kind === "person" && <span className="pill" style={{ background: "#eef0f4", color: "var(--muted)" }}>Person</span>}
                      {r.duplicate && <span className="pill" style={{ background: "#f0efea", color: "var(--muted)" }}>Already saved</span>}
                    </div>
                    <div style={{ fontSize: 11.5, color: "#a9adb4", fontFamily: "Space Grotesk", wordBreak: "break-all" }}>{r.raw_narration}</div>
                  </td>
                  <td>
                    <select className="input" value={cat} disabled={r.duplicate}
                      onChange={(e) => setCategory(r, e.target.value)}
                      aria-label={`Category for ${r.merchant}`}
                      style={{ padding: "8px 10px", fontSize: 13.5, minWidth: 170,
                        ...(needs ? { background: AMBER.bg, borderColor: "#e4c48f", color: AMBER.ink, fontWeight: 600 } : {}) }}>
                      {[...new Set([...categories, cat])].map((c) => <option key={c}>{c}</option>)}
                    </select>
                    {needs && <div style={{ fontSize: 11.5, color: AMBER.ink, marginTop: 4 }}>⚠ Needs a category</div>}
                  </td>
                  <td className="num" style={{ textAlign: "right", fontWeight: 600, whiteSpace: "nowrap",
                    color: r.txn_type === "credit" ? "var(--accent)" : "var(--ink)" }}>
                    {r.txn_type === "credit" ? "+" : "−"}{inr(r.amount)}
                  </td>
                </tr>
              );
            })}
            {!shown.length && <tr><td colSpan={4} style={{ color: "var(--faint)" }}>Nothing needs a category. 🎉</td></tr>}
          </tbody>
        </table>
      </div>

      <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
        <button className="btn btn-ghost" onClick={onCancel} disabled={busy}>Start over</button>
        <button className="btn" onClick={() => onSave(corrections)} disabled={busy}>
          {busy ? "Saving…" : fresh.length ? `Looks good — save ${fresh.length}` : "Nothing new — finish"}
        </button>
      </div>
    </>
  );
}
