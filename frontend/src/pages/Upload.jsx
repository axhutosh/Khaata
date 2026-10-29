import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, inr } from "../api";

export default function Upload() {
  const nav = useNavigate();
  const [file, setFile] = useState(null);
  const [password, setPassword] = useState("");
  const [needPw, setNeedPw] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [result, setResult] = useState(null);

  const go = async () => {
    if (!file) return;
    setBusy(true); setErr("");
    try {
      const res = await api.upload(file, password || undefined);
      setResult(res);
    } catch (e) {
      if (/password protected/i.test(e.message)) { setNeedPw(true); setErr("This PDF is locked. Enter its password."); }
      else setErr(e.message);
    } finally { setBusy(false); }
  };

  return (
    <div style={{ maxWidth: 720, margin: "0 auto", paddingTop: 20 }}>
      <h1 className="grotesk" style={{ fontSize: 28, margin: "0 0 6px" }}>Upload your bank statement</h1>
      <p style={{ color: "var(--muted)", margin: "0 0 28px" }}>
        SBI statement PDF. For the richest insights, upload several months. Parsed, then discarded.
      </p>

      <div className="card" style={{ padding: 24, marginBottom: 18 }}>
        <input type="file" accept="application/pdf" onChange={(e) => { setFile(e.target.files[0]); setResult(null); }} />
        {file && (
          <div style={{ marginTop: 18 }}>
            {needPw && (
              <>
                <label style={{ fontSize: 13.5, fontWeight: 600, display: "block", marginBottom: 8 }}>
                  PDF password
                </label>
                <input className="input" type="password" value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="e.g. PAN in capitals, or name + DOB" style={{ maxWidth: 360, marginBottom: 14 }} />
              </>
            )}
            <div>
              <button className="btn" onClick={go} disabled={busy}>
                {busy ? "Scanning…" : "Unlock & scan"}
              </button>
            </div>
          </div>
        )}
        {err && <p style={{ color: "var(--spend)", fontSize: 13.5, marginTop: 14 }}>{err}</p>}
      </div>

      {result && (
        <div className="card" style={{ padding: 24 }}>
          <div style={{
            background: result.balance_check.reconciles ? "#ecf6f1" : "#fdf3e7",
            border: "1px solid " + (result.balance_check.reconciles ? "#cde7db" : "#f0e2c9"),
            borderRadius: 12, padding: "14px 18px", marginBottom: 18, fontSize: 14,
            color: result.balance_check.reconciles ? "#0a5f4e" : "#92600f",
          }}>
            {result.balance_check.reconciles
              ? <><b>Balance check passed.</b> Opening + credits − debits = closing. Nothing missed.</>
              : <><b>Balance check needs a look.</b> Difference of {result.balance_check.difference}.</>}
          </div>
          <p style={{ fontSize: 15, margin: "0 0 16px" }}>
            Parsed <b>{result.parsed}</b> · saved <b>{result.saved}</b> · duplicates skipped <b>{result.duplicates}</b>
          </p>
          <button className="btn" onClick={() => nav("/")}>See insights →</button>
        </div>
      )}
    </div>
  );
}
