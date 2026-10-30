import { useMemo, useState } from "react";
import { inr, inrExact } from "../api";
import { CategoryDot, QUICK_PICKS } from "../categories";

const AMBER = { bg: "#fdf3e7", line: "#f0e2c9", ink: "#92600f" };
const JADE = { bg: "#ecf6f1", line: "#cde7db", ink: "#0a5f4e" };

// Most UPI payees are local shops no rule can know. Categorise each one once here,
// biggest spend first; the choice becomes a rule for every future upload.
function PayeePanel({ rows, categories, categoryOf, setCategory }) {
  const payees = useMemo(() => {
    const by = new Map();
    for (const r of rows) {
      if (r.duplicate || r.category !== "Uncategorised") continue;
      const p = by.get(r.merchant) || { row: r, merchant: r.merchant, kind: r.counterparty_kind, count: 0, total: 0, sample: r.raw_narration };
      p.count += 1;
      p.total += Number(r.amount);
      by.set(r.merchant, p);
    }
    return [...by.values()].sort((a, b) => b.total - a.total);
  }, [rows]);
  const [showAll, setShowAll] = useState(false);
  if (!payees.length) return null;

  const done = payees.filter((p) => categoryOf(p.row) !== "Uncategorised").length;
  const shown = showAll ? payees : payees.slice(0, 8);

  return (
    <div className="card" style={{ padding: "18px 22px", marginBottom: 18 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, flexWrap: "wrap", marginBottom: 4 }}>
        <h2 style={{ fontSize: 16, margin: 0 }}>Who are these payees?</h2>
        <span className="num" style={{ fontSize: 13, color: done === payees.length ? "var(--accent-dark)" : AMBER.ink, fontWeight: 600 }}>
          {done} of {payees.length} categorised
        </span>
      </div>
      <p style={{ fontSize: 13.5, color: "var(--muted)", margin: "0 0 10px" }}>
        Khaata couldn't tell what these sell. Pick once per payee — it applies to all their payments and is remembered.
      </p>
      <div style={{ height: 6, background: "#f0efea", borderRadius: 4, marginBottom: 6 }} aria-hidden="true">
        <div style={{ width: `${(done / payees.length) * 100}%`, height: "100%", background: "var(--accent)", borderRadius: 4, transition: "width .2s" }} />
      </div>

      {shown.map((p) => {
        const current = categoryOf(p.row);
        const picked = current !== "Uncategorised";
        return (
          <div key={p.merchant} style={{ padding: "14px 0", borderTop: "1px solid #f2f1ec" }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap", marginBottom: 9 }}>
              <span style={{ fontWeight: 600 }}>{p.merchant}</span>
              {p.kind === "person" && <span className="pill" style={{ background: "#eef0f4", color: "var(--muted)" }}>Person</span>}
              <span className="num" style={{ fontSize: 13, color: "var(--muted)" }}>
                {p.count} payment{p.count > 1 ? "s" : ""} · {inr(p.total)}
              </span>
              {picked && <span style={{ fontSize: 12.5, color: "var(--accent-dark)", fontWeight: 600 }}>✓ {current}</span>}
            </div>
            <div style={{ display: "flex", gap: 7, flexWrap: "wrap", alignItems: "center" }} role="group" aria-label={`Category for ${p.merchant}`}>
              {QUICK_PICKS.map((c) => (
                <button key={c} className={"chip" + (current === c ? " on" : "")} aria-pressed={current === c}
                  onClick={() => setCategory(p.row, current === c ? "Uncategorised" : c)}>
                  <CategoryDot category={c} />{c === "Transfer · Person" ? "A person" : c}
                </button>
              ))}
              <select className="chip" value={QUICK_PICKS.includes(current) || !picked ? "" : current}
                onChange={(e) => e.target.value && setCategory(p.row, e.target.value)}
                aria-label={`More categories for ${p.merchant}`}
                style={!QUICK_PICKS.includes(current) && picked ? { background: "var(--ink)", color: "#fff", borderColor: "var(--ink)" } : {}}>
                <option value="">More…</option>
                {categories.filter((c) => !QUICK_PICKS.includes(c) && c !== "Uncategorised").map((c) => <option key={c}>{c}</option>)}
              </select>
            </div>
          </div>
        );
      })}

      {payees.length > 8 && (
        <button className="link-btn" style={{ marginTop: 8, fontSize: 13.5 }} onClick={() => setShowAll(!showAll)}>
          {showAll ? "Show fewer" : `Show all ${payees.length} payees`}
        </button>
      )}
    </div>
  );
}

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

      <PayeePanel rows={rows} categories={categories} categoryOf={categoryOf} setCategory={setCategory} />

      <h2 style={{ fontSize: 15, margin: "4px 0 10px" }}>All transactions</h2>
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

      <div style={{ position: "sticky", bottom: 0, display: "flex", gap: 10, justifyContent: "flex-end", alignItems: "center",
        padding: "14px 0", background: "linear-gradient(to top, var(--ground) 75%, transparent)", flexWrap: "wrap" }}>
        {flagged > 0 && (
          <span style={{ fontSize: 13, color: AMBER.ink, marginRight: "auto" }}>
            {flagged} row{flagged > 1 ? "s" : ""} still uncategorised — fine to save; fix them later in Transactions.
          </span>
        )}
        <button className="btn btn-ghost" onClick={onCancel} disabled={busy}>Start over</button>
        <button className="btn" onClick={() => onSave(corrections)} disabled={busy}>
          {busy ? "Saving…" : fresh.length ? `Looks good — save ${fresh.length}` : "Nothing new — finish"}
        </button>
      </div>
    </>
  );
}
