import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from "recharts";
import { api, inr } from "../api";
import { catColor as color } from "../categories";

export default function Dashboard() {
  const [period, setPeriod] = useState("month");
  const [data, setData] = useState(null);

  useEffect(() => { api.overview(period).then(setData).catch(() => {}); }, [period]);
  if (!data) return <p>Loading…</p>;
  if (!data.kpis.income && !data.kpis.spent)
    return <p>No data yet. <a href="/upload">Upload a statement</a> to get started.</p>;

  const k = data.kpis;

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 26, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 className="grotesk" style={{ fontSize: 26, margin: "0 0 4px" }}>Overview</h1>
          <p style={{ color: "var(--faint)", margin: 0, fontSize: 14 }}>{k.from} → {k.to}</p>
        </div>
        <div style={{ display: "inline-flex", background: "#eeede7", borderRadius: 10, padding: 3 }}>
          {["day", "month", "year"].map((p) => (
            <button key={p} onClick={() => setPeriod(p)}
              style={{ fontFamily: "inherit", fontSize: 13, fontWeight: 600, padding: "7px 14px", borderRadius: 8,
                border: "none", cursor: "pointer",
                background: period === p ? "#fff" : "transparent",
                color: period === p ? "var(--ink)" : "var(--muted)",
                boxShadow: period === p ? "0 1px 2px rgba(0,0,0,.06)" : "none" }}>
              {p[0].toUpperCase() + p.slice(1)}ly
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,minmax(0,1fr))", gap: 16, marginBottom: 16 }}>
        <Kpi label="Income" value={inr(k.income)} />
        <Kpi label="Spent" value={inr(k.spent)} />
        <Kpi label="Saved" value={inr(k.saved)} accent />
        <Kpi label="Savings rate" value={k.savings_rate + "%"} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,1.5fr) minmax(0,1fr)", gap: 16, marginBottom: 16 }}>
        <div className="card" style={{ padding: 22 }}>
          <h2 style={{ fontSize: 15, margin: "0 0 16px" }}>Income vs spend</h2>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data.buckets}>
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#8a9099" }} axisLine={false} tickLine={false} />
              <Tooltip formatter={(v) => inr(v)} />
              <Bar dataKey="income" fill="#0E7C66" radius={[4, 4, 0, 0]} />
              <Bar dataKey="spend" fill="#C2410C" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card" style={{ padding: 22 }}>
          <h2 style={{ fontSize: 15, margin: "0 0 16px" }}>Where it went</h2>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={data.categories} dataKey="amount" nameKey="category" innerRadius={50} outerRadius={85}>
                {data.categories.map((c, i) => <Cell key={i} fill={color(c.category, i)} />)}
              </Pie>
              <Tooltip formatter={(v) => inr(v)} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card" style={{ padding: 22 }}>
        <h2 style={{ fontSize: 15, margin: "0 0 18px" }}>Top merchants</h2>
        {data.top_merchants.map((m, i) => {
          const max = data.top_merchants[0].amount || 1;
          return (
            <div key={i} style={{ marginBottom: 14 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13.5, marginBottom: 6 }}>
                <span style={{ fontWeight: 600 }}>{m.merchant}</span>
                <span className="num" style={{ color: "var(--muted)" }}>{inr(m.amount)} · {m.count}×</span>
              </div>
              <div style={{ height: 7, background: "#f0efea", borderRadius: 4 }}>
                <div style={{ width: (m.amount / max * 100) + "%", height: "100%", background: color(null, i), borderRadius: 4 }} />
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}

function Kpi({ label, value, accent }) {
  return (
    <div className="card" style={{ padding: 18 }}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value num" style={accent ? { color: "var(--accent)" } : {}}>{value}</div>
    </div>
  );
}
