import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";

const GIS_SRC = "https://accounts.google.com/gsi/client";

// Google Identity Services: load the script once, render Google's own button, hand the
// signed ID token to the backend (which verifies it). No Google secrets live in the browser.
function useGoogleButton(clientId, onCredential) {
  const el = useRef(null);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    if (!clientId) return;
    const render = () => {
      if (!window.google?.accounts?.id || !el.current) return;
      window.google.accounts.id.initialize({ client_id: clientId, callback: (r) => onCredential(r.credential),
        ux_mode: "popup", auto_select: false, itp_support: true });
      window.google.accounts.id.renderButton(el.current, { theme: "outline", size: "large", shape: "rectangular",
        text: "continue_with", width: el.current.offsetWidth || 360, logo_alignment: "left" });
      setReady(true);
    };
    if (window.google?.accounts?.id) return render();
    let s = document.querySelector(`script[src="${GIS_SRC}"]`);
    if (!s) {
      s = Object.assign(document.createElement("script"), { src: GIS_SRC, async: true, defer: true });
      document.head.appendChild(s);
    }
    s.addEventListener("load", render);
    return () => s.removeEventListener("load", render);
  }, [clientId]);
  return { el, ready };
}

const PROMISES = [
  ["Reads locked PDFs and Excel", "Your statement password is used once to unlock the file, then forgotten."],
  ["Daily, monthly, yearly", "See where money goes — shops, people, subscriptions — balance-checked to the paisa."],
  ["Yours alone", "Single-user, signed-in access to every number. Nothing is shared."],
];

export default function Login() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState(params.get("expired") ? "Your session ended. Please sign in again." : "");
  const [busy, setBusy] = useState(false);
  const [clientId, setClientId] = useState(null);

  useEffect(() => { api.authConfig().then((c) => setClientId(c.google_client_id)).catch(() => {}); }, []);

  const done = (me) => nav(me.onboarded ? "/" : "/upload", { replace: true });

  const onGoogle = async (credential) => {
    setBusy(true); setErr("");
    try { done(await api.google(credential)); } catch (e) { setErr(e.message); setBusy(false); }
  };
  const { el: googleEl } = useGoogleButton(clientId, onGoogle);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setErr("");
    try { done(await api.login(email.trim(), password)); }
    catch (e) { setErr(e.message); setPassword(""); setBusy(false); }
  };

  return (
    <div style={{ display: "flex", minHeight: "100vh", flexWrap: "wrap" }}>
      <div style={{ flex: "1 1 460px", background: "#16181d", color: "#f7f6f2", padding: "56px 48px",
        display: "flex", flexDirection: "column", justifyContent: "center" }}>
        <div style={{ maxWidth: 420 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 11, marginBottom: 40 }}>
            <div className="logo-mark">K</div>
            <span className="grotesk" style={{ fontWeight: 600, fontSize: 21 }}>Khaata</span>
          </div>
          <h1 className="grotesk" style={{ fontSize: 38, lineHeight: 1.12, margin: "0 0 16px" }}>
            Every rupee, finally accounted for.
          </h1>
          <p style={{ color: "#b9bdc4", fontSize: 16, lineHeight: 1.6, margin: "0 0 34px" }}>
            Upload a bank statement and Khaata turns it into a clear picture of where your money goes.
          </p>
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 18 }}>
            {PROMISES.map(([t, d]) => (
              <li key={t} style={{ display: "flex", gap: 12 }}>
                <span aria-hidden="true" style={{ color: "#5fd0b0", fontWeight: 700 }}>✓</span>
                <span><b style={{ display: "block", fontSize: 15 }}>{t}</b><span style={{ color: "#9aa0a8", fontSize: 14 }}>{d}</span></span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div style={{ flex: "1 1 460px", display: "flex", alignItems: "center", justifyContent: "center", padding: 32 }}>
        <div style={{ width: "100%", maxWidth: 360 }}>
          <h2 className="grotesk" style={{ fontSize: 26, margin: "0 0 6px" }}>Welcome back</h2>
          <p style={{ color: "var(--muted)", fontSize: 14.5, margin: "0 0 26px" }}>Sign in to your Khaata</p>

          {err && <div className="notice notice-error" role="alert" style={{ marginBottom: 18 }}>{err}</div>}

          {clientId && (
            <>
              <div ref={googleEl} style={{ width: "100%", minHeight: 44, display: "flex", justifyContent: "center" }}
                aria-label="Sign in with Google" />
              <div style={{ display: "flex", alignItems: "center", gap: 12, margin: "22px 0", color: "var(--faint)", fontSize: 12.5 }}>
                <span style={{ flex: 1, height: 1, background: "var(--line)" }} />or with email<span style={{ flex: 1, height: 1, background: "var(--line)" }} />
              </div>
            </>
          )}

          <form onSubmit={submit}>
            <label htmlFor="email" style={{ fontSize: 13, fontWeight: 600, display: "block", marginBottom: 7 }}>Email</label>
            <input id="email" className="input" type="email" autoComplete="username" required value={email}
              onChange={(e) => setEmail(e.target.value)} style={{ marginBottom: 18 }} />

            <label htmlFor="password" style={{ fontSize: 13, fontWeight: 600, display: "block", marginBottom: 7 }}>Password</label>
            <input id="password" className="input" type="password" autoComplete="current-password" required value={password}
              onChange={(e) => setPassword(e.target.value)} style={{ marginBottom: 24 }} />

            <button className="btn" style={{ width: "100%", minHeight: 46 }} type="submit" disabled={busy}>
              {busy ? <><span className="spinner" aria-hidden="true" /> Signing in…</> : "Sign in"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
