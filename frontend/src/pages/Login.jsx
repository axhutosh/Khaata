import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import Logo from "../components/Logo";
import { DEFAULT_POLICY, emailCheck, passwordChecks, passwordStrength } from "../passwordRules";

const STRENGTH = [
  { label: "Too weak", color: "#C2410C" }, { label: "Weak", color: "#C2410C" }, { label: "Fair", color: "#B45309" },
  { label: "Good", color: "#0E7C66" }, { label: "Strong", color: "#0A5F4E" },
];

function StrengthMeter({ password, email, policy }) {
  const checks = passwordChecks(password, email, policy);
  const score = passwordStrength(password, email, policy);
  const s = STRENGTH[score];
  return (
    <div id="pw-rules" style={{ marginTop: 10 }}>
      {password && (
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
          <div style={{ flex: 1, display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 4 }} aria-hidden="true">
            {[1, 2, 3, 4].map((i) => (
              <span key={i} style={{ height: 6, borderRadius: 3, background: i <= Math.max(score, 1) ? s.color : "#e6e4de" }} />
            ))}
          </div>
          <span role="status" style={{ fontSize: 12.5, fontWeight: 600, color: s.color, minWidth: 64, textAlign: "right" }}>
            {s.label}
          </span>
        </div>
      )}
      <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 5 }} aria-label="Password requirements">
        {checks.map((c) => {
          const state = !password ? "todo" : c.ok ? "ok" : "bad";
          return (
            <li key={c.label} style={{ display: "flex", gap: 8, fontSize: 12.5, lineHeight: 1.4,
              color: state === "ok" ? "var(--accent-dark)" : state === "bad" ? "#92600f" : "var(--faint)" }}>
              <span aria-hidden="true" style={{ width: 14, flex: "0 0 auto", fontWeight: 700 }}>
                {state === "ok" ? "✓" : state === "bad" ? "✗" : "•"}
              </span>
              <span>{c.label}<span className="sr-only">{state === "ok" ? " — done" : state === "bad" ? " — not yet" : ""}</span></span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

const PROMISES = [
  ["Reads locked PDFs and Excel", "Your statement password is used once to unlock the file, then forgotten."],
  ["Daily, monthly, yearly", "Shops, people, subscriptions — every statement balance-checked to the paisa."],
  ["Private by design", "Your own Khaata, sealed off from everyone else's. Bank details encrypted at rest."],
];

export default function Login() {
  const nav = useNavigate();
  const loc = useLocation();
  const [params] = useSearchParams();
  const signup = loc.pathname === "/signup";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [err, setErr] = useState(params.get("expired") ? "Your session ended. Please sign in again." : "");
  const [busy, setBusy] = useState(false);
  const [openSignup, setOpenSignup] = useState(true);
  const [policy, setPolicy] = useState(DEFAULT_POLICY);
  const [emailTouched, setEmailTouched] = useState(false);

  useEffect(() => {
    api.authConfig().then((c) => { setOpenSignup(c.open_signup); if (c.password_policy) setPolicy(c.password_policy); })
      .catch(() => {});
  }, []);
  useEffect(() => { setErr(""); setPassword(""); setEmailTouched(false); }, [signup]);

  const mail = emailCheck(email);
  const showEmailError = emailTouched && mail.error;
  const pwOk = !signup || passwordChecks(password, email, policy).every((c) => c.ok);

  const submit = async (e) => {
    e.preventDefault();
    setEmailTouched(true);
    if (mail.error) return setErr(mail.error);
    if (!pwOk) return setErr("Your password doesn't meet every requirement yet — see the list below it.");
    setBusy(true); setErr("");
    try {
      const me = await (signup ? api.signup : api.login)(email.trim(), password);
      nav(me.onboarded ? "/" : "/upload", { replace: true });
    } catch (e) {
      setErr(e.message); setBusy(false);
      if (!signup) setPassword("");
    }
  };

  const tab = (active) => ({
    flex: 1, textAlign: "center", padding: "9px 0", borderRadius: 8, fontSize: 14, fontWeight: 600, textDecoration: "none",
    background: active ? "#fff" : "transparent", color: active ? "var(--ink)" : "var(--muted)",
    boxShadow: active ? "0 1px 2px rgba(0,0,0,.06)" : "none",
  });

  return (
    <div style={{ display: "flex", minHeight: "100vh", flexWrap: "wrap" }}>
      <div style={{ flex: "1 1 460px", background: "#16181d", color: "#f7f6f2", padding: "56px 48px",
        display: "flex", flexDirection: "column", justifyContent: "center" }}>
        <div style={{ maxWidth: 420 }}>
          <div style={{ marginBottom: 40 }}><Logo size={38} text={23} onDark /></div>
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
          <h2 className="grotesk" style={{ fontSize: 26, margin: "0 0 6px" }}>{signup ? "Create your Khaata" : "Welcome back"}</h2>
          <p style={{ color: "var(--muted)", fontSize: 14.5, margin: "0 0 22px" }}>
            {signup ? "Free, private, and yours alone." : "Sign in to your Khaata"}
          </p>

          <nav aria-label="Sign in or create an account" style={{ display: "flex", gap: 4, background: "#eeede7", borderRadius: 10, padding: 3, marginBottom: 22 }}>
            <Link to="/login" replace style={tab(!signup)} aria-current={!signup ? "page" : undefined}>Sign in</Link>
            <Link to="/signup" replace style={tab(signup)} aria-current={signup ? "page" : undefined}>Create account</Link>
          </nav>

          {signup && !openSignup && (
            <div className="notice" style={{ background: "#eef0f4", border: "1px solid #dfe3ea", color: "#374151", marginBottom: 16 }}>
              New accounts are invite-only right now. If you've been invited, use that email.
            </div>
          )}
          {err && <div className="notice notice-error" role="alert" style={{ marginBottom: 16 }}>{err}</div>}

          <form onSubmit={submit} noValidate>
            <label htmlFor="email" style={{ fontSize: 13, fontWeight: 600, display: "block", marginBottom: 7 }}>Email</label>
            <input id="email" className="input" type="email" inputMode="email" autoComplete="email" required value={email}
              placeholder="you@example.com" spellCheck={false} autoCapitalize="none"
              aria-invalid={showEmailError ? true : undefined} aria-describedby="email-msg"
              onChange={(e) => setEmail(e.target.value)} onBlur={() => email && setEmailTouched(true)}
              style={showEmailError ? { borderColor: "var(--spend)" } : undefined} />
            <div id="email-msg" style={{ minHeight: 18, margin: "6px 0 10px", fontSize: 12.5 }}>
              {showEmailError && <span style={{ color: "#9a3412" }}>✗ {mail.error}</span>}
              {!mail.error && mail.suggestion && signup && (
                <span style={{ color: "var(--muted)" }}>
                  Did you mean{" "}
                  <button type="button" className="link-btn" onClick={() => setEmail(mail.suggestion)}>{mail.suggestion}</button>?
                </span>
              )}
            </div>

            <label htmlFor="password" style={{ fontSize: 13, fontWeight: 600, display: "block", marginBottom: 7 }}>Password</label>
            <div style={{ position: "relative" }}>
              <input id="password" className="input" type={show ? "text" : "password"} required value={password}
                autoComplete={signup ? "new-password" : "current-password"} aria-describedby={signup ? "pw-rules" : undefined}
                onChange={(e) => setPassword(e.target.value)} style={{ paddingRight: 70 }} />
              <button type="button" className="link-btn" onClick={() => setShow(!show)} aria-label={show ? "Hide password" : "Show password"}
                style={{ position: "absolute", right: 14, top: "50%", transform: "translateY(-50%)", fontSize: 13 }}>
                {show ? "Hide" : "Show"}
              </button>
            </div>
            {signup && <StrengthMeter password={password} email={email} policy={policy} />}

            <button className="btn" style={{ width: "100%", minHeight: 46, marginTop: 24 }} type="submit"
              disabled={busy || !email || !password || (signup && (!pwOk || !!mail.error))}>
              {busy ? <><span className="spinner" aria-hidden="true" /> {signup ? "Creating account…" : "Signing in…"}</>
                : signup ? "Create account" : "Sign in"}
            </button>
          </form>

          <p style={{ fontSize: 13.5, color: "var(--muted)", margin: "20px 0 0", textAlign: "center" }}>
            {signup ? <>Already have an account? <Link to="/login" replace>Sign in</Link></>
              : <>New to Khaata? <Link to="/signup" replace>Create an account</Link></>}
          </p>
        </div>
      </div>
    </div>
  );
}
