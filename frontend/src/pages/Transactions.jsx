import { useEffect, useMemo, useState } from "react";
import { api, inr } from "../api";
import { CAT_COLORS, catColor } from "../categories.jsx";

const CATEGORIES = Object.keys(CAT_COLORS);
const iso = (d) => d.toISOString().slice(0, 10);
const dayLabel = (s) => new Date(s + "T00:00:00").toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short", year: "numeric" });

function Segmented({ value, onChange, options, label }) {
  return (
    <div role="group" aria-label={label} style={{ display: "inline-flex", background: "#eeede7", borderRadius: 10, padding: 3 }}>
      {options.map(([v, text]) => (
        <button key={v} type="button" onClick={() => onChange(v)} aria-pressed={value === v}
          style={{ fontFamily: "inherit", fontSize: 13, fontWeight: 600, padding: "7px 12px", borderRadius: 8, border: "none",
            cursor: "pointer", minHeight: 34, whiteSpace: "nowrap",
            background: value === v ? "#fff" : "transparent", color: value === v ? "var(--ink)" : "var(--muted)",
            boxShadow: value === v ? "0 1px 2px rgba(0,0,0,.06)" : "none" }}>
          {text}
        </button>
      ))}
    </div>
  );
}

function Stat({ label, value, tone }) {
  return (
    <div style={{ minWidth: 110 }}>
      <div style={{ fontSize: 12, color: "var(--faint)", marginBottom: 3 }}>{label}</div>
      <div className="num grotesk" style={{ fontWeight: 600, fontSize: 18, color: tone }}>{value}</div>
    </div>
  );
}

function TxnRow({ r, onCategory, saving }) {
  const [open, setOpen] = useState(false);
  const needs = r.category === "Uncategorised";
  const credit = r.type === "credit";
  return (
    <div style={{ borderTop: "1px solid #f2f1ec" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "12px 18px", flexWrap: "wrap" }}>
        <button onClick={() => setOpen(!open)} aria-expanded={open} aria-label={`Details for ${r.merchant}`}
          style={{ all: "unset", cursor: "pointer", display: "flex", alignItems: "center", gap: 12, flex: "1 1 260px", minWidth: 0 }}>
          <span className="grotesk" aria-hidden="true" style={{ width: 34, height: 34, borderRadius: 10, flex: "0 0 auto",
            display: "inline-flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 14,
            color: "#fff", background: catColor(r.category) }}>
            {r.merchant[0]?.toUpperCase()}
          </span>
          <span style={{ minWidth: 0 }}>
            <span style={{ display: "flex", gap: 7, alignItems: "center", flexWrap: "wrap" }}>
              <span style={{ fontWeight: 600, fontSize: 14 }}>{r.merchant}</span>
              {r.kind === "person" && <span className="pill" style={{ background: "#f4ecf4", color: "#7a2d78" }}>Person</span>}
            </span>
            <span style={{ display: "block", fontSize: 12, color: "var(--faint)" }}>{r.method} · {credit ? "Money in" : "Money out"}</span>
          </span>
        </button>
        <select className="input" value={r.category} disabled={saving} onChange={(e) => onCategory(r, e.target.value)}
          aria-label={`Category for ${r.merchant}`}
          style={{ padding: "7px 10px", fontSize: 13, width: 180, flex: "0 0 auto",
            ...(needs ? { background: "#fdf3e7", borderColor: "#e4c48f", color: "#92600f", fontWeight: 600 } : {}) }}>
          {[...new Set([...CATEGORIES, r.category])].map((c) => <option key={c}>{c}</option>)}
        </select>
        <span style={{ textAlign: "right", width: 120, flex: "0 0 auto" }}>
          <span className="num" style={{ display: "block", fontWeight: 600, fontSize: 14.5, color: credit ? "var(--accent-dark)" : "var(--ink)" }}>
            {credit ? "+" : "−"}{inr(r.amount)}
          </span>
          <span className="num" style={{ fontSize: 11.5, color: "var(--faint)" }}>Bal {inr(r.balance)}</span>
        </span>
      </div>
      {open && (
        <div style={{ padding: "0 18px 14px 66px", fontSize: 12.5, color: "var(--muted)", display: "grid", gap: 4 }}>
          <div><span style={{ color: "var(--faint)" }}>Narration</span> <span style={{ fontFamily: "Space Grotesk", wordBreak: "break-all" }}>{r.raw}</span></div>
          <div><span style={{ color: "var(--faint)" }}>From</span> {r.source}</div>
          <div style={{ color: "var(--faint)" }}>Changing the category updates every payment to {r.merchant} and is remembered for future uploads.</div>
        </div>
      )}
    </div>
  );
}

export default function Transactions() {
  const [rows, setRows] = useState(null);
  const [latest, setLatest] = useState(null);
  const [q, setQ] = useState("");
  const [query, setQuery] = useState(""); // debounced q
  const [range, setRange] = useState("all");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [type, setType] = useState("");
  const [kind, setKind] = useState("");
  const [category, setCategory] = useState("");
  const [saving, setSaving] = useState(null);
  const [rerun, setRerun] = useState(null);

  useEffect(() => { api.transactions({ limit: 1 }).then((r) => setLatest(r[0]?.date || null)).catch(() => {}); }, []);
  useEffect(() => { const t = setTimeout(() => setQuery(q.trim()), 300); return () => clearTimeout(t); }, [q]);

  // date presets are relative to the newest transaction, since statements lag the calendar
  const dates = useMemo(() => {
    if (range === "custom") return { start: from, end: to };
    if (!latest || range === "all") return {};
    const end = new Date(latest + "T00:00:00");
    if (range === "month") return { start: iso(new Date(end.getFullYear(), end.getMonth(), 1)), end: latest };
    return { start: iso(new Date(end - 29 * 864e5)), end: latest };
  }, [range, from, to, latest]);

  const params = useMemo(() => {
    const p = { limit: 5000 };
    if (query) p.q = query;
    if (type) p.type = type;
    if (kind) p.kind = kind;
    if (category) p.category = category;
    if (dates.start) p.start = dates.start;
    if (dates.end) p.end = dates.end;
    return p;
  }, [query, type, kind, category, dates]);

  const load = () => api.transactions(params).then(setRows).catch(() => setRows([]));
  useEffect(() => { load(); }, [params]);

  const onCategory = async (r, c) => {
    setSaving(r.id);
    try { await api.recategorize(r.id, c); await load(); } finally { setSaving(null); }
  };
  const reclassify = async () => {
    setRerun("busy");
    try { const r = await api.reclassify(); setRerun(r.changed); await load(); } catch { setRerun(null); }
  };
  const clear = () => { setQ(""); setRange("all"); setType(""); setKind(""); setCategory(""); };
  const filtered = query || range !== "all" || type || kind || category;

  const days = useMemo(() => {
    const by = new Map();
    for (const r of rows || []) {
      const d = by.get(r.date) || { date: r.date, rows: [], in: 0, out: 0 };
      d.rows.push(r);
      d[r.type === "credit" ? "in" : "out"] += r.amount;
      by.set(r.date, d);
    }
    return [...by.values()];
  }, [rows]);

  const sum = (t) => (rows || []).filter((r) => r.type === t).reduce((s, r) => s + r.amount, 0);
  const totalIn = sum("credit"), totalOut = sum("debit");
  const uncat = (rows || []).filter((r) => r.category === "Uncategorised").length;

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

      <div className="card" style={{ padding: 16, marginBottom: 14, display: "grid", gap: 12 }}>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
          <input className="input" type="search" placeholder="Search merchant, person or narration" value={q}
            onChange={(e) => setQ(e.target.value)} style={{ flex: "1 1 260px", maxWidth: 420, padding: "10px 13px" }}
            aria-label="Search transactions" />
          <select className="input" value={range} onChange={(e) => setRange(e.target.value)} aria-label="Date range"
            style={{ width: 170, padding: "10px 12px", fontSize: 14 }}>
            <option value="all">All time</option>
            <option value="month">Latest month</option>
            <option value="30">Last 30 days</option>
            <option value="custom">Custom range…</option>
          </select>
          {range === "custom" && (
            <>
              <input className="input" type="date" value={from} onChange={(e) => setFrom(e.target.value)} aria-label="From date" style={{ width: 160, padding: "9px 10px" }} />
              <span style={{ color: "var(--faint)" }}>to</span>
              <input className="input" type="date" value={to} onChange={(e) => setTo(e.target.value)} aria-label="To date" style={{ width: 160, padding: "9px 10px" }} />
            </>
          )}
        </div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
          <Segmented label="Direction" value={type} onChange={setType} options={[["", "All"], ["debit", "Money out"], ["credit", "Money in"]]} />
          <Segmented label="Counterparty" value={kind} onChange={setKind} options={[["", "Everyone"], ["merchant", "Merchants"], ["person", "People"]]} />
          <select className="input" value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Category"
            style={{ width: 200, padding: "8px 12px", fontSize: 13.5, ...(category === "Uncategorised" ? { borderColor: "#e4c48f", background: "#fdf3e7" } : {}) }}>
            <option value="">All categories</option>
            {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
          </select>
          {filtered && <button className="link-btn" onClick={clear} style={{ fontSize: 13.5 }}>Clear filters</button>}
        </div>
      </div>

      {rows && (
        <div className="card" style={{ padding: "14px 18px", marginBottom: 14, display: "flex", gap: 22, flexWrap: "wrap", alignItems: "center" }}>
          <Stat label="Transactions" value={rows.length} />
          <Stat label="Money in" value={"+" + inr(totalIn)} tone="var(--accent-dark)" />
          <Stat label="Money out" value={"−" + inr(totalOut)} />
          <Stat label="Net" value={(totalIn - totalOut >= 0 ? "+" : "−") + inr(Math.abs(totalIn - totalOut))}
            tone={totalIn - totalOut >= 0 ? "var(--accent-dark)" : "var(--spend)"} />
          {uncat > 0 && category !== "Uncategorised" && (
            <button className="chip" onClick={() => setCategory("Uncategorised")} style={{ marginLeft: "auto", borderColor: "#e4c48f", color: "#92600f", background: "#fdf3e7" }}>
              ⚠ {uncat} need a category
            </button>
          )}
        </div>
      )}

      {rows === null ? <p style={{ color: "var(--muted)" }}>Loading…</p> : !rows.length ? (
        <div className="card" style={{ padding: 28, color: "var(--muted)" }}>
          No transactions match.{filtered && <> <button className="link-btn" onClick={clear}>Clear filters</button></>}
        </div>
      ) : (
        <div className="card" style={{ overflow: "clip" }}>
          {days.map((d) => (
            <section key={d.date} aria-label={dayLabel(d.date)}>
              <div style={{ position: "sticky", top: 0, zIndex: 1, display: "flex", justifyContent: "space-between", gap: 10,
                padding: "9px 18px", background: "#fbfaf6", borderTop: "1px solid #f0efea", fontSize: 12.5 }}>
                <span style={{ fontWeight: 600, color: "var(--muted)" }}>{dayLabel(d.date)}</span>
                <span className="num" style={{ color: "var(--faint)" }}>
                  {d.out > 0 && <>−{inr(d.out)} out</>}{d.out > 0 && d.in > 0 && " · "}
                  {d.in > 0 && <span style={{ color: "var(--accent-dark)" }}>+{inr(d.in)} in</span>}
                </span>
              </div>
              {d.rows.map((r) => <TxnRow key={r.id} r={r} onCategory={onCategory} saving={saving === r.id} />)}
            </section>
          ))}
        </div>
      )}
    </>
  );
}
