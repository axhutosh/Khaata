import { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { api } from "../api";

const svg = (d) => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9"
    strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{d}</svg>
);

const ICONS = {
  dashboard: svg(<><rect x="3" y="3" width="7" height="9" rx="1.5" /><rect x="14" y="3" width="7" height="5" rx="1.5" /><rect x="14" y="12" width="7" height="9" rx="1.5" /><rect x="3" y="16" width="7" height="5" rx="1.5" /></>),
  transactions: svg(<><path d="M4 7h13M13 3l4 4-4 4" /><path d="M20 17H7M11 13l-4 4 4 4" /></>),
  subscriptions: svg(<><path d="M20 11a8 8 0 1 0-2.3 5.7" /><path d="M20 4v7h-7" /><path d="M12 8v4l2.5 1.5" /></>),
  budgets: svg(<><path d="M12 3a9 9 0 1 0 9 9h-9z" /><path d="M15 3.5A9 9 0 0 1 20.5 9H15z" /></>),
  upload: svg(<><path d="M12 15V4M7 9l5-5 5 5" /><path d="M4 15v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4" /></>),
  logout: svg(<><path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3" /><path d="M10 16l-4-4 4-4M6 12h10" /></>),
};

const items = [
  { to: "/", label: "Dashboard", icon: "dashboard", end: true },
  { to: "/transactions", label: "Transactions", icon: "transactions" },
  { to: "/subscriptions", label: "Subscriptions", icon: "subscriptions" },
  { to: "/budgets", label: "Budgets", icon: "budgets" },
];

export default function Shell({ children }) {
  const nav = useNavigate();
  const [me, setMe] = useState(null);
  useEffect(() => { api.me().then(setMe).catch(() => {}); }, []);
  const logout = async () => { await api.logout(); nav("/login"); };

  return (
    <div className="shell">
      <aside className="sidebar" aria-label="Main">
        <div className="sidebar-brand">
          <div className="logo-mark">K</div>
          <span className="grotesk" style={{ fontWeight: 600, fontSize: 19, letterSpacing: "-.01em" }}>Khaata</span>
        </div>

        <nav className="sidebar-nav">
          {items.map((it) => (
            <NavLink key={it.to} to={it.to} end={it.end} className={({ isActive }) => "nav" + (isActive ? " on" : "")}>
              {ICONS[it.icon]}<span>{it.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-foot">
          <NavLink to="/upload" className="btn btn-dark sidebar-upload" style={{ textDecoration: "none" }}>
            {ICONS.upload}<span>Upload statement</span>
          </NavLink>
          <div className="sidebar-user">
            <span className="sidebar-avatar grotesk" aria-hidden="true">{(me?.email || "?")[0].toUpperCase()}</span>
            <span className="sidebar-email" title={me?.email}>{me?.email || "…"}</span>
            <button className="icon-btn" onClick={logout} aria-label="Sign out" title="Sign out">{ICONS.logout}</button>
          </div>
        </div>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}
