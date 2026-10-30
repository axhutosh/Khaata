import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import Logo from "../components/Logo";

const GIS_SRC = "https://accounts.google.com/gsi/client";

// Google Identity Services: load the script once, render Google's own button, hand the
// signed ID token to the backend (which verifies it). No Google secrets live in the browser.
function useGoogleButton(clientId, onCredential) {
  const el = useRef(null);
  const [state, setState] = useState("loading"); // loading | ready | failed
  useEffect(() => {
    if (!clientId) return;
    const render = () => {
      if (!window.google?.accounts?.id || !el.current) return setState("failed");
      window.google.accounts.id.initialize({ client_id: clientId, callback: (r) => onCredential(r.credential),
        ux_mode: "popup", auto_select: false, itp_support: true });
      window.google.accounts.id.renderButton(el.current, { theme: "filled_black", size: "large", shape: "pill",
        text: "continue_with", width: Math.min(el.current.offsetWidth || 340, 400), logo_alignment: "left" });
      setState("ready");
    };
    if (window.google?.accounts?.id) return render();
    let s = document.querySelector(`script[src="${GIS_SRC}"]`);
    if (!s) {
      s = Object.assign(document.createElement("script"), { src: GIS_SRC, async: true, defer: true });
      document.head.appendChild(s);
    }
    const fail = () => setState("failed");
    s.addEventListener("load", render);
    s.addEventListener("error", fail);
    return () => { s.removeEventListener("load", render); s.removeEventListener("error", fail); };
  }, [clientId]);
  return { el, state };
}

const PROMISES = [
  ["Reads locked PDFs and Excel", "Your statement password is used once to unlock the file, then forgotten."],
  ["Daily, monthly, yearly", "Shops, people, subscriptions — every statement balance-checked to the paisa."],
  ["Private by design", "Your own Khaata, sealed off from everyone else's. No passwords, nothing shared."],
];

export default function Login() {
  const nav = useNavigate();
  const [params] = useSearchParams();
  const [err, setErr] = useState(params.get("expired") ? "Your session ended. Please sign in again." : "");
  const [busy, setBusy] = useState(false);
  const [clientId, setClientId] = useState(undefined); // undefined = still asking the server

  useEffect(() => { api.authConfig().then((c) => setClientId(c.google_client_id)).catch(() => setClientId(null)); }, []);

  const onGoogle = async (credential) => {
    setBusy(true); setErr("");
    try {
      const me = await api.google(credential);
      nav(me.onboarded ? "/" : "/upload", { replace: true });
    } catch (e) { setErr(e.message); setBusy(false); }
  };
  const { el, state } = useGoogleButton(clientId, onGoogle);

  return (
    <div style={{ display: "flex", minHeight: "100vh", flexWrap: "wrap" }}>
      <div style={{ flex: "1 1 460px", background: "#16181d", color: "#f7f6f2", padding: "56px 48px",
        display: "flex", flexDirection: "column", justifyContent: "center" }}>
        <div style={{ maxWidth: 420 }}>
          <div style={{ marginBottom: 40 }}>
            <Logo size={38} text={23} onDark />
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
          <h2 className="grotesk" style={{ fontSize: 26, margin: "0 0 6px" }}>Welcome to Khaata</h2>
          <p style={{ color: "var(--muted)", fontSize: 14.5, margin: "0 0 26px", lineHeight: 1.55 }}>
            Sign in with Google to continue. New here? The same button creates your account.
          </p>

          {err && <div className="notice notice-error" role="alert" style={{ marginBottom: 18 }}>{err}</div>}

          {clientId === null ? (
            <div className="notice notice-error" role="alert">
              Sign-in isn't set up yet: add <code>GOOGLE_CLIENT_ID</code> to <code>backend/.env</code> and restart the backend.
            </div>
          ) : (
            <>
              <div ref={el} aria-label="Continue with Google"
                style={{ width: "100%", minHeight: 44, display: "flex", justifyContent: "center", opacity: busy ? 0.5 : 1,
                  pointerEvents: busy ? "none" : "auto" }} />
              {(clientId === undefined || state === "loading") && (
                <p style={{ textAlign: "center", color: "var(--faint)", fontSize: 13.5, margin: "10px 0 0" }}>Loading Google sign-in…</p>
              )}
              {state === "failed" && (
                <div className="notice notice-error" role="alert" style={{ marginTop: 12 }}>
                  Couldn't load Google sign-in. Check your connection or ad blocker, then reload the page.
                </div>
              )}
              {busy && <p style={{ textAlign: "center", color: "var(--muted)", fontSize: 13.5, margin: "12px 0 0" }}>Signing you in…</p>}
            </>
          )}

          <p style={{ fontSize: 12.5, color: "var(--faint)", margin: "28px 0 0", lineHeight: 1.6 }}>
            Every Google account gets its own private Khaata — nobody else can see your statements.
            Google shares just your name and email, never your Google password.
          </p>
        </div>
      </div>
    </div>
  );
}
