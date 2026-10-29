import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import Review from "./Review";

const STEPS = ["Upload", "Unlock", "Review", "Insights"];

function StepRail({ at }) {
  return (
    <ol style={{ display: "flex", gap: 8, listStyle: "none", padding: 0, margin: "0 0 26px", flexWrap: "wrap" }}>
      {STEPS.map((s, i) => (
        <li key={s} aria-current={i === at ? "step" : undefined}
          style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13.5,
            fontWeight: i === at ? 600 : 500, color: i <= at ? "var(--ink)" : "var(--faint)" }}>
          <span className="num" style={{ width: 24, height: 24, borderRadius: 999, display: "inline-flex",
            alignItems: "center", justifyContent: "center", fontSize: 12,
            background: i < at ? "var(--accent)" : i === at ? "var(--ink)" : "#ebe9e3",
            color: i <= at ? "#fff" : "var(--muted)" }}>
            {i < at ? "✓" : i + 1}
          </span>
          {s}
          {i < STEPS.length - 1 && <span style={{ color: "#d0cec7", margin: "0 4px" }}>—</span>}
        </li>
      ))}
    </ol>
  );
}

function PastUploads({ uploads, onDelete }) {
  if (!uploads.length) return null;
  return (
    <div className="card" style={{ padding: "8px 24px", marginTop: 18 }}>
      <h2 style={{ fontSize: 15, margin: "14px 0 6px" }}>Previous uploads</h2>
      {uploads.map((u) => (
        <div key={u.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 0", borderTop: "1px solid #f2f1ec", fontSize: 14 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis" }}>{u.filename}</div>
            <div className="num" style={{ fontSize: 12.5, color: "var(--muted)" }}>
              {u.from} → {u.to} · {u.saved} saved{u.duplicates ? ` · ${u.duplicates} duplicates` : ""}
              {u.reconciles ? " · ✓ balanced" : " · ⚠ didn't balance"}
            </div>
          </div>
          <button className="btn btn-ghost" style={{ padding: "8px 14px", fontSize: 13 }} onClick={() => onDelete(u)}>Delete</button>
        </div>
      ))}
    </div>
  );
}

export default function Upload() {
  const nav = useNavigate();
  const [me, setMe] = useState(null);
  const [file, setFile] = useState(null);
  const [password, setPassword] = useState("");
  const [needPw, setNeedPw] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [preview, setPreview] = useState(null);
  const [uploads, setUploads] = useState([]);

  const loadUploads = () => api.uploads().then(setUploads).catch(() => {});
  useEffect(() => { api.me().then(setMe).catch(() => {}); loadUploads(); }, []);

  const reset = () => { setFile(null); setPassword(""); setNeedPw(false); setPreview(null); setErr(""); };

  const scan = async () => {
    if (!file) return;
    setBusy(true); setErr("");
    try {
      setPreview(await api.preview(file, password || undefined));
      setPassword(""); // used once; drop it
    } catch (e) {
      if (/password protected/i.test(e.message)) { setNeedPw(true); setErr("This PDF is locked. Enter its password."); }
      else if (/password/i.test(e.message)) { setNeedPw(true); setErr("That password didn't work. Try again."); }
      else setErr(e.message);
    } finally { setBusy(false); }
  };

  const save = async (corrections) => {
    setBusy(true); setErr("");
    try {
      await api.commit(preview.token, corrections);
      nav("/");
    } catch (e) { setErr(e.message); setBusy(false); }
  };

  const remove = async (u) => {
    if (!window.confirm(`Delete "${u.filename}" and the ${u.saved} transactions it saved?`)) return;
    await api.deleteUpload(u.id);
    loadUploads();
    api.me().then(setMe).catch(() => {});
  };

  const step = preview ? 2 : needPw ? 1 : 0;

  return (
    <div style={{ maxWidth: preview ? 1040 : 720, margin: "0 auto", padding: "28px 20px 56px" }}>
      {me?.onboarded && <Link to="/" style={{ fontSize: 14, display: "inline-block", marginBottom: 18 }}>← Back to dashboard</Link>}
      <StepRail at={step} />

      {preview ? (
        <>
          <h1 className="grotesk" style={{ fontSize: 28, margin: "0 0 6px" }}>Review before saving</h1>
          <p style={{ color: "var(--muted)", margin: "0 0 22px" }}>
            {preview.filename} · fix any categories, then save. Corrections are remembered for future uploads.
          </p>
          {err && <p style={{ color: "var(--spend)", fontSize: 13.5 }}>{err}</p>}
          <Review preview={preview} busy={busy} onSave={save} onCancel={reset} />
        </>
      ) : (
        <>
          <h1 className="grotesk" style={{ fontSize: 28, margin: "0 0 6px" }}>Upload your bank statement</h1>
          <p style={{ color: "var(--muted)", margin: "0 0 28px" }}>
            SBI statement PDF. For the richest insights, upload several months. Parsed, then discarded.
          </p>

          <div className="card" style={{ padding: 24 }}>
            <input type="file" accept="application/pdf"
              onChange={(e) => { setFile(e.target.files[0]); setNeedPw(false); setErr(""); }} />
            {file && (
              <div style={{ marginTop: 18 }}>
                {needPw && (
                  <>
                    <label htmlFor="pdf-pw" style={{ fontSize: 13.5, fontWeight: 600, display: "block", marginBottom: 8 }}>
                      PDF password
                    </label>
                    <input id="pdf-pw" className="input" type="password" value={password} autoFocus
                      onChange={(e) => setPassword(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && scan()}
                      placeholder="e.g. PAN in capitals, or name + DOB" style={{ maxWidth: 360, marginBottom: 8 }} />
                    <p style={{ fontSize: 12.5, color: "var(--faint)", margin: "0 0 14px" }}>
                      Used once to unlock the file, never stored.
                    </p>
                  </>
                )}
                <button className="btn" onClick={scan} disabled={busy || (needPw && !password)}>
                  {busy ? "Scanning…" : needPw ? "Unlock & scan" : "Scan statement"}
                </button>
              </div>
            )}
            {err && <p style={{ color: "var(--spend)", fontSize: 13.5, marginTop: 14 }}>{err}</p>}
          </div>

          <PastUploads uploads={uploads} onDelete={remove} />
        </>
      )}
    </div>
  );
}
