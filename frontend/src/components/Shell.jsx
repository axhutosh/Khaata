import { NavLink, useNavigate } from "react-router-dom";
import { api } from "../api";

const items = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/transactions", label: "Transactions" },
  { to: "/subscriptions", label: "Subscriptions" },
  { to: "/budgets", label: "Budgets" },
];

export default function Shell({ children }) {
  const nav = useNavigate();
  const logout = async () => { await api.logout(); nav("/login"); };

  return (
    <div className="shell">
      <aside className="sidebar">
        <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "4px 10px 26px" }}>
          <div className="logo-mark">K</div>
          <span className="grotesk" style={{ fontWeight: 600, fontSize: 19, letterSpacing: "-.01em" }}>Khaata</span>
        </div>
        <nav style={{ display: "flex", flexDirection: "column", gap: 3, flex: 1 }}>
          {items.map((it) => (
            <NavLink key={it.to} to={it.to} end={it.end}
              className={({ isActive }) => "nav" + (isActive ? " on" : "")}>
              {it.label}
            </NavLink>
          ))}
        </nav>
        <NavLink to="/upload" className="btn btn-dark" style={{ marginBottom: 14, textDecoration: "none" }}>
          Upload statement
        </NavLink>
        <button className="nav" onClick={logout} style={{ border: "none", background: "none", textAlign: "left" }}>
          Sign out
        </button>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}
