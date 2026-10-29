import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

export default function Login() {
  const nav = useNavigate();
  const [email, setEmail] = useState("you@email.com");
  const [password, setPassword] = useState("password");
  const [err, setErr] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    try {
      const me = await api.login(email, password);
      nav(me.onboarded ? "/" : "/upload");
    } catch (e) { setErr(e.message); }
  };

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <div style={{ flex: "1 1 520px", background: "#16181d", color: "#f7f6f2", padding: 56,
        display: "flex", flexDirection: "column", justifyContent: "center" }}>
        <div style={{ maxWidth: 420 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 11, marginBottom: 40 }}>
            <div className="logo-mark">K</div>
            <span className="grotesk" style={{ fontWeight: 600, fontSize: 21 }}>Khaata</span>
          </div>
          <h1 className="grotesk" style={{ fontSize: 38, lineHeight: 1.12, margin: "0 0 16px" }}>
            Every rupee, finally accounted for.
          </h1>
          <p style={{ color: "#b9bdc4", fontSize: 16, lineHeight: 1.6, margin: 0 }}>
            Upload a bank statement and Khaata turns it into a clear picture of where your money goes.
          </p>
        </div>
      </div>
      <div style={{ flex: "1 1 560px", display: "flex", alignItems: "center", justifyContent: "center", padding: 32 }}>
        <form onSubmit={submit} style={{ width: "100%", maxWidth: 360 }}>
          <h2 className="grotesk" style={{ fontSize: 26, margin: "0 0 6px" }}>Welcome back</h2>
          <p style={{ color: "var(--muted)", fontSize: 14.5, margin: "0 0 28px" }}>Sign in to your Khaata</p>

          <label style={{ fontSize: 13, fontWeight: 600, display: "block", marginBottom: 7 }}>Email</label>
          <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} style={{ marginBottom: 18 }} />

          <label style={{ fontSize: 13, fontWeight: 600, display: "block", marginBottom: 7 }}>Password</label>
          <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} style={{ marginBottom: 24 }} />

          {err && <p style={{ color: "var(--spend)", fontSize: 13.5, margin: "0 0 16px" }}>{err}</p>}
          <button className="btn" style={{ width: "100%" }} type="submit">Sign in</button>
        </form>
      </div>
    </div>
  );
}
