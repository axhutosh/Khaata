import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend, LineChart, Line, ReferenceDot,
  ResponsiveContainer, PieChart, Pie, Cell, Tooltip,
} from "recharts";
import { api, inr } from "../api";
import { catColor } from "../categories.jsx";

// validated (dataviz validator): CVD-separable, >=3:1 on white, chroma above the gray floor
const IN = "#0B8F6E";
const OUT = "#C2410C";
const FLOW = {
  merchants: { label: "Shops & services", color: "#C2410C" },
  people: { label: "People (P2P)", color: "#9F3A9C" },
  investments: { label: "Investments", color: "#1A8F5E" },
  cash_fees: { label: "Cash & bank fees", color: "#B08A2E" },
};
const FLOW_IN = { income: "Income", people: "From people", other: "Refunds & other" };
const GRID = "#efeee9";
const AXIS = { fontSize: 11, fill: "#8a9099" };
const compact = (n) => (n >= 1e5 ? `₹${(n / 1e5).toFixed(1)}L` : n >= 1e3 ? `₹${(n / 1e3).toFixed(n >= 1e4 ? 0 : 1)}k` : `₹${n}`);
const pct = (a, b) => (b ? Math.round((a / b) * 100) : 0);
const fmtDate = (s) => new Date(s + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" });

function Card({ title, sub, children, style }) {
  return (
    <section className="card" style={{ padding: 22, minWidth: 0, ...style }}>
      {title && <h2 style={{ fontSize: 15, margin: sub ? "0 0 2px" : "0 0 16px" }}>{title}</h2>}
      {sub && <p style={{ fontSize: 12.5, color: "var(--faint)", margin: "0 0 16px" }}>{sub}</p>}
      {children}
    </section>
  );
}

function Kpi({ label, value, sub, tone }) {
  return (
    <div className="card" style={{ padding: 18 }}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value num" style={tone ? { color: tone } : {}}>{value}</div>
      {sub && <div className="num" style={{ fontSize: 12.5, color: "var(--muted)", marginTop: 6 }}>{sub}</div>}
    </div>
  );
}

const TONE = {
  warn: { icon: "!", bg: "#fdf3e7", ink: "#92600f", label: "Heads-up" },
  good: { icon: "✓", bg: "#ecf6f1", ink: "#0a5f4e", label: "Good" },
  info: { icon: "i", bg: "#eef0f4", ink: "#4b5563", label: "Note" },
};

function Noticed({ notes }) {
  if (!notes.length) return null;
  return (
    <Card title="What Khaata noticed" style={{ marginBottom: 16 }}>
      <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 10 }}>
        {notes.map((n, i) => {
          const t = TONE[n.tone] || TONE.info;
          return (
            <li key={i} style={{ display: "flex", gap: 12, alignItems: "flex-start", fontSize: 14, lineHeight: 1.5 }}>
              <span aria-label={t.label} title={t.label} className="grotesk" style={{ width: 22, height: 22, borderRadius: 999, flex: "0 0 auto",
                display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 700,
                background: t.bg, color: t.ink, marginTop: 1 }}>{t.icon}</span>
              <span>{n.text}</span>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

function LegendRow({ color, label, value, share }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13.5, padding: "5px 0" }}>
      <span aria-hidden="true" style={{ width: 10, height: 10, borderRadius: 3, background: color, flex: "0 0 auto" }} />
      <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{label}</span>
      <span className="num" style={{ fontWeight: 600 }}>{inr(value)}</span>
      {share !== undefined && <span className="num" style={{ color: "var(--faint)", width: 38, textAlign: "right" }}>{share}%</span>}
    </div>
  );
}

// one 100% bar split by flow, with a 2px surface gap between segments
function FlowBar({ flows, total }) {
  const parts = flows.filter((f) => f.amount > 0);
  return (
    <div style={{ display: "flex", gap: 2, height: 14, borderRadius: 4, overflow: "hidden", margin: "4px 0 14px", background: "#f0efea" }}>
      {parts.map((f) => (
        <div key={f.key} title={`${FLOW[f.key].label}: ${inr(f.amount)}`}
          style={{ width: `${(f.amount / total) * 100}%`, background: FLOW[f.key].color }} />
      ))}
    </div>
  );
}

function MoneyOut({ flows, total, flowsIn, totalIn }) {
  return (
    <Card title="Where your money went" sub={`${inr(total)} out · ${inr(totalIn)} in`}>
      <FlowBar flows={flows} total={total} />
      {flows.map((f) => <LegendRow key={f.key} color={FLOW[f.key].color} label={FLOW[f.key].label} value={f.amount} share={pct(f.amount, total)} />)}
      <div style={{ borderTop: "1px solid #f2f1ec", marginTop: 10, paddingTop: 10 }}>
        <div className="kpi-label" style={{ marginBottom: 4 }}>Money in came from</div>
        {flowsIn.filter((f) => f.amount > 0).map((f) => (
          <div key={f.key} style={{ display: "flex", justifyContent: "space-between", fontSize: 13.5, padding: "3px 0" }}>
            <span>{FLOW_IN[f.key]}</span>
            <span className="num" style={{ fontWeight: 600 }}>{inr(f.amount)} <span style={{ color: "var(--faint)", fontWeight: 400 }}>{pct(f.amount, totalIn)}%</span></span>
          </div>
        ))}
      </div>
    </Card>
  );
}

function Categories({ categories }) {
  // a donut reads at most ~6 slices: keep the top 6, fold the rest into "Other"
  const top = categories.slice(0, 6);
  const rest = categories.slice(6).reduce((s, c) => s + c.amount, 0);
  const data = rest ? [...top, { category: "Other", amount: rest }] : top;
  const total = data.reduce((s, c) => s + c.amount, 0);
  const col = (c) => (c === "Other" ? "#c9ccd1" : catColor(c));
  return (
    <Card title="Spending by category" sub="Shops & services only — P2P, investments and cash are separate">
      {!data.length ? <p style={{ color: "var(--faint)", fontSize: 14 }}>No spending yet.</p> : (
        <div style={{ display: "flex", gap: 18, alignItems: "center", flexWrap: "wrap" }}>
          <div style={{ width: 170, height: 170, flex: "0 0 auto" }}>
            <ResponsiveContainer>
              <PieChart>
                <Pie data={data} dataKey="amount" nameKey="category" innerRadius={52} outerRadius={80}
                  stroke="#fff" strokeWidth={2} isAnimationActive={false}>
                  {data.map((c) => <Cell key={c.category} fill={col(c.category)} />)}
                </Pie>
                <Tooltip formatter={(v) => inr(v)} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div style={{ flex: 1, minWidth: 200 }}>
            {data.map((c) => <LegendRow key={c.category} color={col(c.category)} label={c.category} value={c.amount} share={pct(c.amount, total)} />)}
          </div>
        </div>
      )}
    </Card>
  );
}

function BarList({ items, color, empty }) {
  if (!items.length) return <p style={{ color: "var(--faint)", fontSize: 14, margin: 0 }}>{empty}</p>;
  const max = Math.max(...items.map((i) => i.value)) || 1;
  return items.map((it) => (
    <div key={it.label} style={{ marginBottom: 13 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 10, fontSize: 13.5, marginBottom: 6 }}>
        <span style={{ fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{it.label}</span>
        <span className="num" style={{ color: "var(--muted)", whiteSpace: "nowrap" }}>{it.detail}</span>
      </div>
      <div style={{ height: 7, background: "#f0efea", borderRadius: 4 }}>
        <div style={{ width: `${(it.value / max) * 100}%`, height: "100%", background: color, borderRadius: 4 }} />
      </div>
    </div>
  ));
}

function People({ people }) {
  return (
    <Card title="People you transact with" sub="UPI transfers to and from people (P2P)">
      {!people.length ? <p style={{ color: "var(--faint)", fontSize: 14, margin: 0 }}>No P2P transfers found.</p> : (
        <table style={{ fontSize: 13.5 }}>
          <thead><tr><th style={{ paddingLeft: 0 }}>Person</th><th style={{ textAlign: "right" }}>Sent</th><th style={{ textAlign: "right", paddingRight: 0 }}>Received</th></tr></thead>
          <tbody>
            {people.map((p) => (
              <tr key={p.name}>
                <td style={{ paddingLeft: 0, fontWeight: 600 }}>{p.name} <span style={{ color: "var(--faint)", fontWeight: 400 }}>· {p.count}×</span></td>
                <td className="num" style={{ textAlign: "right" }}>{p.sent ? "−" + inr(p.sent) : "—"}</td>
                <td className="num" style={{ textAlign: "right", paddingRight: 0, color: p.received ? "var(--accent-dark)" : "var(--faint)" }}>
                  {p.received ? "+" + inr(p.received) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

function Weekday({ weekday, small }) {
  return (
    <Card title="When you spend" sub="Shops & services, by day of the week">
      <ResponsiveContainer width="100%" height={170}>
        <BarChart data={weekday} margin={{ top: 4, right: 0, left: -18, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis dataKey="day" tick={AXIS} axisLine={false} tickLine={false} />
          <YAxis tick={AXIS} axisLine={false} tickLine={false} tickFormatter={compact} width={52} />
          <Tooltip cursor={{ fill: "#f4f3ee" }} formatter={(v, _n, p) => [`${inr(v)} · ${p.payload.count} payments`, "Spent"]} />
          <Bar dataKey="amount" fill={OUT} radius={[4, 4, 0, 0]} maxBarSize={28} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
      <div style={{ display: "flex", gap: 14, alignItems: "baseline", borderTop: "1px solid #f2f1ec", marginTop: 12, paddingTop: 12, flexWrap: "wrap" }}>
        <span className="kpi-value num" style={{ fontSize: 22 }}>{small.count}</span>
        <span style={{ fontSize: 13.5, color: "var(--muted)" }}>
          small payments (₹{small.threshold} or less) — <b className="num" style={{ color: "var(--ink)" }}>{inr(small.total)}</b> total, {small.share}% of all payments
        </span>
      </div>
    </Card>
  );
}

function Balance({ balance, low }) {
  return (
    <Card title="Balance over time" sub={`Lowest: ${inr(low.balance)} on ${fmtDate(low.date)}`}>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={balance} margin={{ top: 8, right: 8, left: -14, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis dataKey="date" tick={AXIS} axisLine={false} tickLine={false} tickFormatter={fmtDate} minTickGap={24} />
          <YAxis tick={AXIS} axisLine={false} tickLine={false} tickFormatter={compact} width={56} />
          <Tooltip labelFormatter={fmtDate} formatter={(v) => [inr(v), "Closing balance"]} />
          <Line type="linear" dataKey="balance" stroke={IN} strokeWidth={2} dot={false} activeDot={{ r: 4 }} isAnimationActive={false} />
          <ReferenceDot x={low.date} y={low.balance} r={5} fill={OUT} stroke="#fff" strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}

function Largest({ largest }) {
  return (
    <Card title="Largest payments" sub="Shops & services">
      {largest.map((l, i) => (
        <div key={i} style={{ display: "flex", gap: 12, alignItems: "baseline", padding: "8px 0", borderTop: i ? "1px solid #f2f1ec" : "none", fontSize: 13.5 }}>
          <span className="num" style={{ color: "var(--faint)", width: 52 }}>{fmtDate(l.date)}</span>
          <span style={{ flex: 1, minWidth: 0 }}>
            <span style={{ fontWeight: 600 }}>{l.merchant}</span>
            <span style={{ color: "var(--faint)" }}> · {l.category}</span>
          </span>
          <span className="num" style={{ fontWeight: 600 }}>{inr(l.amount)}</span>
        </div>
      ))}
    </Card>
  );
}

export default function Dashboard() {
  const [period, setPeriod] = useState("month");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => { api.overview(period).then(setData).catch((e) => setError(e.message)); }, [period]);
  if (error) return <div className="notice notice-error">Couldn't load your insights: {error}</div>;
  if (!data) return <p style={{ color: "var(--muted)" }}>Loading…</p>;
  if (data.empty)
    return (
      <div className="card" style={{ padding: 32, maxWidth: 520 }}>
        <h1 className="grotesk" style={{ fontSize: 22, margin: "0 0 8px" }}>No transactions yet</h1>
        <p style={{ color: "var(--muted)", margin: "0 0 18px" }}>Upload an SBI statement to see where your money goes.</p>
        <Link to="/upload" className="btn" style={{ textDecoration: "none" }}>Upload a statement</Link>
      </div>
    );

  const k = data.kpis;
  const topMerchants = data.top_merchants.map((m) => ({ label: m.merchant, value: m.amount, detail: `${inr(m.amount)} · ${m.count}×` }));

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 22, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 className="grotesk" style={{ fontSize: 26, margin: "0 0 4px" }}>Overview</h1>
          <p className="num" style={{ color: "var(--faint)", margin: 0, fontSize: 14 }}>
            {fmtDate(k.from)} → {fmtDate(k.to)} · {k.days} days · {k.txn_count} transactions
          </p>
        </div>
        <div role="group" aria-label="Trend period" style={{ display: "inline-flex", background: "#eeede7", borderRadius: 10, padding: 3 }}>
          {["day", "month", "year"].map((p) => (
            <button key={p} onClick={() => setPeriod(p)} aria-pressed={period === p}
              style={{ fontFamily: "inherit", fontSize: 13, fontWeight: 600, padding: "7px 14px", borderRadius: 8,
                border: "none", cursor: "pointer", minHeight: 34,
                background: period === p ? "#fff" : "transparent",
                color: period === p ? "var(--ink)" : "var(--muted)",
                boxShadow: period === p ? "0 1px 2px rgba(0,0,0,.06)" : "none" }}>
              {p === "day" ? "Daily" : p[0].toUpperCase() + p.slice(1) + "ly"}
            </button>
          ))}
        </div>
      </div>

      <div className="grid-kpis">
        <Kpi label="Money in" value={inr(k.money_in)}
          sub={k.income ? `Income ${inr(k.income)} · from people ${inr(k.p2p_received)}` : `From people ${inr(k.p2p_received)}`} />
        <Kpi label="Money out" value={inr(k.money_out)}
          sub={<span style={{ color: k.net >= 0 ? "var(--accent-dark)" : "var(--spend)" }}>{k.net >= 0 ? "Up " : "Down "}{inr(Math.abs(k.net))} net</span>} />
        <Kpi label="Spent at shops & services" value={inr(k.spent)} sub={`≈ ${inr(k.daily_avg)} a day`} tone={OUT} />
        <Kpi label="Sent to people (P2P)" value={inr(k.p2p_sent)} sub={`Received ${inr(k.p2p_received)} back`} tone={FLOW.people.color} />
      </div>

      <Noticed notes={data.noticed} />

      <div className="grid-2">
        <Card title="Money in vs out" sub={period === "day" ? "Per day" : period === "year" ? "Per year" : "Per month"}>
          <ResponsiveContainer width="100%" height={230}>
            <BarChart data={data.buckets} margin={{ top: 4, right: 0, left: -14, bottom: 0 }} barGap={2}>
              <CartesianGrid vertical={false} stroke={GRID} />
              <XAxis dataKey="label" tick={AXIS} axisLine={false} tickLine={false} minTickGap={12} />
              <YAxis tick={AXIS} axisLine={false} tickLine={false} tickFormatter={compact} width={56} />
              <Tooltip cursor={{ fill: "#f4f3ee" }} formatter={(v, n) => [inr(v), n]} />
              <Legend iconType="square" iconSize={10} wrapperStyle={{ fontSize: 12.5, color: "var(--muted)" }} />
              <Bar name="Money in" dataKey="money_in" fill={IN} radius={[4, 4, 0, 0]} maxBarSize={26} isAnimationActive={false} />
              <Bar name="Money out" dataKey="money_out" fill={OUT} radius={[4, 4, 0, 0]} maxBarSize={26} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <MoneyOut flows={data.flows_out} total={k.money_out} flowsIn={data.flows_in} totalIn={k.money_in} />
      </div>

      <div className="grid-2">
        <Categories categories={data.categories} />
        <Card title="Top merchants">
          <BarList items={topMerchants} color={OUT} empty="No merchant spending yet." />
        </Card>
      </div>

      <div className="grid-2">
        <People people={data.people} />
        <Weekday weekday={data.weekday} small={data.small_spends} />
      </div>

      <div className="grid-2">
        <Balance balance={data.balance} low={data.low_balance} />
        <Largest largest={data.largest} />
      </div>
    </>
  );
}
