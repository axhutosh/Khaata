import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, inr } from "../api";
import { catColor } from "../categories.jsx";

const fmt = (s) => new Date(s + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" });
const daysBetween = (a, b) => Math.round((new Date(b) - new Date(a)) / 864e5);

const SECTIONS = [
  { title: "Subscriptions & bills", sub: "Services, bills, EMIs and insurance that charge on a schedule",
    kinds: ["subscription", "bill", "emi", "insurance", "regular"] },
  { title: "Investments", sub: "SIPs and other scheduled investing — wealth, not spend", kinds: ["investment"] },
  { title: "Regular transfers to people", sub: "P2P payments that repeat, like rent or family support", kinds: ["transfer"] },
  { title: "Regular money in", sub: "Salary and other credits that repeat", kinds: ["income"] },
];
const KIND_LABEL = { subscription: "Subscription", bill: "Bill", emi: "EMI / loan", insurance: "Insurance",
  regular: "Regular payment", investment: "Investment", transfer: "Transfer", income: "Income" };

function Pill({ children, tone = "neutral", title }) {
  const t = {
    neutral: ["#f0efea", "var(--muted)"], good: ["#ecf6f1", "#0a5f4e"], warn: ["#fdf3e7", "#92600f"],
    up: ["#fdf0ea", "#9a3412"], info: ["#eef0f4", "#4b5563"],
  }[tone];
  return <span className="pill" title={title} style={{ background: t[0], color: t[1] }}>{children}</span>;
}

function Status({ item, asOf }) {
  if (item.status === "stopped")
    return <Pill tone="warn" title="No payment where the next one was expected">⏸ May have stopped · last {fmt(item.last_date)}</Pill>;
  const d = daysBetween(asOf, item.next_date);
  if (item.status === "due_soon")
    return <Pill tone="warn">⏰ Due {d <= 0 ? "now" : `in ${d} day${d > 1 ? "s" : ""}`} · {fmt(item.next_date)}</Pill>;
  return <Pill tone="neutral">Next ≈ {fmt(item.next_date)}</Pill>;
}

function Row({ item, asOf }) {
  const [open, setOpen] = useState(false);
  const up = item.price_change && item.price_change.diff > 0;
  const down = item.price_change && item.price_change.diff < 0;
  return (
    <div style={{ borderTop: "1px solid #f2f1ec" }}>
      <button onClick={() => setOpen(!open)} aria-expanded={open}
        style={{ all: "unset", boxSizing: "border-box", width: "100%", cursor: "pointer", display: "flex", gap: 14,
          alignItems: "center", padding: "16px 22px" }}>
        <span className="grotesk" aria-hidden="true" style={{ width: 38, height: 38, borderRadius: 11, flex: "0 0 auto",
          display: "inline-flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 15,
          color: "#fff", background: catColor(item.category) }}>
          {item.merchant[0]?.toUpperCase()}
        </span>
        <span style={{ flex: 1, minWidth: 0 }}>
          <span style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 5 }}>
            <span style={{ fontWeight: 600, fontSize: 14.5 }}>{item.merchant}</span>
            <Pill>{item.cadence}</Pill>
            {item.confidence === "likely"
              ? <Pill tone="info" title={item.reason}>Likely</Pill>
              : <Pill tone="good" title={item.reason}>✓ Confirmed</Pill>}
            {item.kind === "investment" && <Pill tone="good">Wealth, not spend</Pill>}
            {up && <Pill tone="up" title={`Was ${inr(item.price_change.from)}`}>↑ {inr(item.price_change.diff)} price rise</Pill>}
            {down && <Pill tone="good" title={`Was ${inr(item.price_change.from)}`}>↓ {inr(-item.price_change.diff)} cheaper</Pill>}
          </span>
          <span style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", fontSize: 12.5, color: "var(--faint)" }}>
            <Status item={item} asOf={asOf} />
            <span>{KIND_LABEL[item.kind]} · {item.category} · {item.occurrences} payment{item.occurrences > 1 ? "s" : ""}</span>
          </span>
        </span>
        <span style={{ textAlign: "right", flex: "0 0 auto" }}>
          <span className="num grotesk" style={{ display: "block", fontWeight: 600, fontSize: 16 }}>
            {item.direction === "in" ? "+" : ""}{inr(item.amount)}
          </span>
          {item.cadence !== "Monthly" && (
            <span className="num" style={{ fontSize: 12, color: "var(--faint)" }}>≈ {inr(item.monthly)}/mo</span>
          )}
        </span>
        <span aria-hidden="true" style={{ color: "var(--faint)", transform: open ? "rotate(90deg)" : "none", transition: "transform .15s" }}>›</span>
      </button>
      {open && (
        <div style={{ padding: "0 22px 16px 74px", fontSize: 13 }}>
          <p style={{ margin: "0 0 10px", color: "var(--muted)" }}>Why: {item.reason}.</p>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {item.history.map((h) => (
              <span key={h.date} className="num" style={{ background: "#f7f6f2", border: "1px solid var(--line)",
                borderRadius: 8, padding: "6px 10px" }}>
                {fmt(h.date)} · <b>{inr(h.amount)}</b>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Kpi({ label, value, sub }) {
  return (
    <div className="card" style={{ padding: 18 }}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value num">{value}</div>
      {sub && <div style={{ fontSize: 12.5, color: "var(--muted)", marginTop: 6 }}>{sub}</div>}
    </div>
  );
}

export default function Subscriptions() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { api.recurring().then(setData).catch((e) => setErr(e.message)); }, []);

  if (err) return <div className="notice notice-error">Couldn't load recurring payments: {err}</div>;
  if (!data) return <p style={{ color: "var(--muted)" }}>Loading…</p>;

  const t = data.totals;
  const hasAny = data.items.length || data.frequent.length;

  return (
    <>
      <h1 className="grotesk" style={{ fontSize: 26, margin: "0 0 4px" }}>Subscriptions & recurring</h1>
      <p style={{ color: "var(--faint)", margin: "0 0 20px", fontSize: 14 }}>
        Found by spotting payments that repeat at a steady interval with a similar amount
        {data.as_of && <> · statements up to {fmt(data.as_of)}</>}
      </p>

      {data.months_covered > 0 && data.months_covered < 2 && (
        <div className="notice" style={{ background: "#eef0f4", border: "1px solid #dfe3ea", color: "#374151", marginBottom: 18 }}>
          <b>You've uploaded {data.months_covered} month.</b> A pattern needs at least two payments, so most
          subscriptions can't be confirmed yet. Known services (Netflix, SIPs, auto-debits) show as <i>Likely</i> until then.{" "}
          <Link to="/upload">Add more months</Link> for a fuller picture.
        </div>
      )}

      {data.items.length > 0 && (
        <div className="grid-kpis">
          <Kpi label="Subscriptions & bills" value={`${inr(t.subscriptions)}/mo`} sub={`${t.count} active`} />
          <Kpi label="Investing" value={`${inr(t.investments)}/mo`} sub="SIPs — not counted as spend" />
          <Kpi label="Regular transfers" value={`${inr(t.transfers)}/mo`} sub="To people (P2P)" />
          <Kpi label="Price rises" value={t.price_rises} sub={t.price_rises ? "Check the ↑ items below" : "None spotted"} />
        </div>
      )}

      {SECTIONS.map((s) => {
        const rows = data.items.filter((i) => s.kinds.includes(i.kind));
        if (!rows.length) return null;
        return (
          <section key={s.title} className="card" style={{ marginBottom: 16, overflow: "hidden" }}>
            <div style={{ padding: "18px 22px 12px" }}>
              <h2 style={{ fontSize: 15, margin: "0 0 2px" }}>{s.title}</h2>
              <p style={{ fontSize: 12.5, color: "var(--faint)", margin: 0 }}>{s.sub}</p>
            </div>
            {rows.map((i) => <Row key={i.merchant + i.direction} item={i} asOf={data.as_of} />)}
          </section>
        );
      })}

      {data.frequent.length > 0 && (
        <section className="card" style={{ marginBottom: 16, padding: "18px 22px 8px" }}>
          <h2 style={{ fontSize: 15, margin: "0 0 2px" }}>Places you pay often</h2>
          <p style={{ fontSize: 12.5, color: "var(--faint)", margin: "0 0 8px" }}>
            Not on a schedule, so not subscriptions — but they add up
          </p>
          <table style={{ fontSize: 13.5 }}>
            <thead><tr>
              <th style={{ paddingLeft: 0 }}>Merchant</th><th style={{ textAlign: "right" }}>Visits</th>
              <th style={{ textAlign: "right" }}>Average</th><th style={{ textAlign: "right", paddingRight: 0 }}>Total</th>
            </tr></thead>
            <tbody>
              {data.frequent.map((f) => (
                <tr key={f.merchant}>
                  <td style={{ paddingLeft: 0 }}>
                    <div style={{ fontWeight: 600 }}>{f.merchant}</div>
                    <div style={{ fontSize: 12, color: "var(--faint)" }}>{f.category} · last {fmt(f.last_date)}</div>
                  </td>
                  <td className="num" style={{ textAlign: "right" }}>{f.count} <span style={{ color: "var(--faint)" }}>· {f.per_week}/wk</span></td>
                  <td className="num" style={{ textAlign: "right" }}>{inr(f.average)}</td>
                  <td className="num" style={{ textAlign: "right", paddingRight: 0, fontWeight: 600 }}>{inr(f.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {!hasAny && (
        <div className="card" style={{ padding: 28, color: "var(--muted)" }}>
          No repeating payments found yet. Upload two or more months of statements and Khaata will spot
          subscriptions, bills, SIPs and regular transfers automatically.
        </div>
      )}
    </>
  );
}
