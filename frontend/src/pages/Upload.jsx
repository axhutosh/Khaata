import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import Review from "./Review";

const STEPS = ["Upload", "Unlock", "Review", "Insights"];
const ACCEPT = ".pdf,.xls,.xlsx,application/pdf,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
const MAX_MB = 15;

const Icon = {
  upload: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 16V4M7 9l5-5 5 5" /><path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
    </svg>
  ),
  lock: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="4" y="11" width="16" height="10" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </svg>
  ),
  check: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M5 12l5 5L20 7" />
    </svg>
  ),
};

const kindOf = (name) => (/\.xlsx?$/i.test(name) ? "XLS" : "PDF");
const sizeOf = (b) => (b > 1e6 ? (b / 1e6).toFixed(1) + " MB" : Math.max(1, Math.round(b / 1e3)) + " KB");

function StepRail({ at }) {
  return (
    <ol style={{ display: "flex", gap: 8, listStyle: "none", padding: 0, margin: "0 0 28px", flexWrap: "wrap" }}>
      {STEPS.map((s, i) => (
        <li key={s} aria-current={i === at ? "step" : undefined}
          style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13.5,
            fontWeight: i === at ? 600 : 500, color: i <= at ? "var(--ink)" : "var(--faint)" }}>
          <span className="num" style={{ width: 24, height: 24, borderRadius: 999, display: "inline-flex",
            alignItems: "center", justifyContent: "center", fontSize: 12,
            background: i < at ? "var(--accent)" : i === at ? "var(--ink)" : "#ebe9e3",
            color: i <= at ? "#fff" : "var(--muted)" }}>
            {i < at ? Icon.check : i + 1}
          </span>
          {s}
          {i < STEPS.length - 1 && <span aria-hidden="true" style={{ width: 18, height: 1, background: "#d6d4cc", margin: "0 2px" }} />}
        </li>
      ))}
    </ol>
  );
}

function DropZone({ onFile }) {
  const input = useRef(null);
  const [over, setOver] = useState(false);
  const pick = (f) => f && onFile(f);
  return (
    <div className={"dropzone" + (over ? " over" : "")} role="button" tabIndex={0}
      aria-label="Choose a statement file: PDF or Excel"
      onClick={() => input.current.click()}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), input.current.click())}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); pick(e.dataTransfer.files[0]); }}>
      <span className="icon-tile">{Icon.upload}</span>
      <div style={{ fontWeight: 600, fontSize: 15.5 }}>Drop your SBI statement here</div>
      <div style={{ fontSize: 14, color: "var(--muted)" }}>
        or <span style={{ color: "var(--accent)", fontWeight: 600 }}>browse your files</span>
      </div>
      <div style={{ fontSize: 12.5, color: "var(--faint)" }}>PDF or Excel (.xls, .xlsx) · several months is best</div>
      <input ref={input} type="file" accept={ACCEPT} hidden onChange={(e) => { pick(e.target.files[0]); e.target.value = ""; }} />
    </div>
  );
}

function FileChip({ file, onChange, disabled }) {
  const kind = kindOf(file.name);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "14px 16px", border: "1px solid var(--line)",
      borderRadius: 12, background: "#fbfaf6" }}>
      <span className="icon-tile grotesk" style={{ width: 42, height: 42, fontSize: 12, fontWeight: 700,
        background: kind === "PDF" ? "#fdf0ea" : "#eaf3ec", color: kind === "PDF" ? "#9a3412" : "#2f6b3a" }}>
        {kind}
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600, fontSize: 14.5, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{file.name}</div>
        <div className="num" style={{ fontSize: 12.5, color: "var(--faint)" }}>{sizeOf(file.size)}</div>
      </div>
      <button className="link-btn" onClick={onChange} disabled={disabled}>Change</button>
    </div>
  );
}

function PasswordField({ value, onChange, onSubmit, wrong }) {
  const [show, setShow] = useState(false);
  return (
    <div style={{ marginTop: 18 }}>
      <label htmlFor="pdf-pw" style={{ fontSize: 13.5, fontWeight: 600, display: "flex", alignItems: "center", gap: 7, marginBottom: 8 }}>
        {Icon.lock} This PDF is locked — enter its password
      </label>
      <div style={{ position: "relative" }}>
        <input id="pdf-pw" className="input" type={show ? "text" : "password"} value={value} autoFocus
          autoComplete="off" spellCheck={false} aria-invalid={wrong || undefined} aria-describedby="pw-hint"
          onChange={(e) => onChange(e.target.value)} onKeyDown={(e) => e.key === "Enter" && value && onSubmit()}
          style={{ paddingRight: 74, ...(wrong ? { borderColor: "var(--spend)" } : {}) }} />
        <button type="button" className="link-btn" onClick={() => setShow(!show)}
          aria-label={show ? "Hide password" : "Show password"}
          style={{ position: "absolute", right: 14, top: "50%", transform: "translateY(-50%)", fontSize: 13 }}>
          {show ? "Hide" : "Show"}
        </button>
      </div>
      <p id="pw-hint" style={{ fontSize: 12.5, color: "var(--muted)", margin: "8px 0 0", lineHeight: 1.55 }}>
        The SBI email or download screen tells you the format. For emailed statements it's usually the
        <b> last 5 digits of your registered mobile + date of birth as DDMMYY</b>.
        Used once to unlock the file, never stored.
      </p>
    </div>
  );
}

function PastUploads({ uploads, onDelete }) {
  if (!uploads.length) return null;
  return (
    <div className="card" style={{ padding: "6px 24px", marginTop: 18 }}>
      <h2 style={{ fontSize: 14, margin: "14px 0 4px", color: "var(--muted)", fontWeight: 600 }}>Previous uploads</h2>
      {uploads.map((u) => (
        <div key={u.id} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 0", borderTop: "1px solid #f2f1ec", fontSize: 14 }}>
          <span className="icon-tile grotesk" style={{ width: 34, height: 34, fontSize: 10.5, fontWeight: 700, background: "#f0efea", color: "var(--muted)" }}>
            {kindOf(u.filename)}
          </span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{u.filename}</div>
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
  const [wrongPw, setWrongPw] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [preview, setPreview] = useState(null);
  const [uploads, setUploads] = useState([]);

  const loadUploads = () => api.uploads().then(setUploads).catch(() => {});
  useEffect(() => { api.me().then(setMe).catch(() => {}); loadUploads(); }, []);

  const choose = (f) => {
    setErr(""); setNeedPw(false); setWrongPw(false); setPassword("");
    if (!/\.(pdf|xlsx?)$/i.test(f.name)) { setFile(null); setErr("That isn't a PDF or Excel file. Download the statement from SBI as PDF or Excel."); return; }
    if (f.size > MAX_MB * 1e6) { setFile(null); setErr(`That file is over ${MAX_MB} MB. Try a shorter date range.`); return; }
    setFile(f);
  };
  const reset = () => { setFile(null); setPassword(""); setNeedPw(false); setWrongPw(false); setPreview(null); setErr(""); };

  const scan = async () => {
    if (!file) return;
    setBusy(true); setErr(""); setWrongPw(false);
    try {
      setPreview(await api.preview(file, password || undefined));
      setPassword(""); // used once; drop it
    } catch (e) {
      if (/password protected/i.test(e.message)) setNeedPw(true);
      else if (/password/i.test(e.message)) { setNeedPw(true); setWrongPw(true); setErr("That password didn't unlock the file. Check the format and try again."); }
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
    <div style={{ minHeight: "100vh", padding: "28px 20px 56px" }}>
      <div style={{ maxWidth: preview ? 1080 : 600, margin: "0 auto" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 28 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div className="logo-mark">K</div>
            <span className="grotesk" style={{ fontWeight: 600, fontSize: 19 }}>Khaata</span>
          </div>
          {me?.onboarded && <Link to="/" style={{ fontSize: 14, fontWeight: 600 }}>← Back to dashboard</Link>}
        </div>

        <StepRail at={step} />

        {preview ? (
          <>
            <h1 className="grotesk" style={{ fontSize: 28, margin: "0 0 6px" }}>Review before saving</h1>
            <p style={{ color: "var(--muted)", margin: "0 0 22px" }}>
              {preview.filename} · nothing is saved until you press save. Categories you pick are remembered for future uploads.
            </p>
            {err && <div className="notice notice-error" role="alert" style={{ marginBottom: 16 }}>{err}</div>}
            <Review preview={preview} busy={busy} onSave={save} onCancel={reset} />
          </>
        ) : (
          <>
            <h1 className="grotesk" style={{ fontSize: 28, margin: "0 0 6px" }}>
              {me?.onboarded ? "Add a statement" : "Upload your bank statement"}
            </h1>
            <p style={{ color: "var(--muted)", margin: "0 0 24px", lineHeight: 1.55 }}>
              Download it from SBI (net banking or YONO) as PDF or Excel. Khaata reads it, checks every rupee
              adds up, and lets you review before anything is saved.
            </p>

            <div className="card" style={{ padding: 24 }}>
              {file ? <FileChip file={file} onChange={reset} disabled={busy} /> : <DropZone onFile={choose} />}

              {file && needPw && (
                <PasswordField value={password} onChange={(v) => { setPassword(v); setWrongPw(false); }}
                  onSubmit={scan} wrong={wrongPw} />
              )}

              {err && <div className="notice notice-error" role="alert" style={{ marginTop: 16 }}>{err}</div>}

              {file && (
                <button className="btn" onClick={scan} disabled={busy || (needPw && !password)}
                  style={{ width: "100%", marginTop: 18, minHeight: 46 }}>
                  {busy ? <><span className="spinner" aria-hidden="true" /> Reading your statement…</>
                    : needPw ? "Unlock & read statement" : "Read statement"}
                </button>
              )}
            </div>

            <ul style={{ listStyle: "none", padding: 0, margin: "16px 0 0", display: "flex", gap: 18, flexWrap: "wrap",
              fontSize: 12.5, color: "var(--muted)" }}>
              {["Password never stored", "File discarded after reading", "Balance-checked to the paisa"].map((t) => (
                <li key={t} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ color: "var(--accent)" }}>{Icon.check}</span>{t}
                </li>
              ))}
            </ul>

            <PastUploads uploads={uploads} onDelete={remove} />
          </>
        )}
      </div>
    </div>
  );
}
