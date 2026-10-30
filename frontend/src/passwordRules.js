// Rules for a NEW password — the same checks as backend/app/passwords.py, with the word list
// and lengths fetched from the server (/auth/config), so the form shows exactly what the
// server will accept. Never used at sign-in.

const LEET = { 0: "o", 1: "i", 3: "e", 4: "a", 5: "s", 7: "t", 8: "b", "@": "a", $: "s", "!": "i", "|": "i", "+": "t" };
const ROWS = ["qwertyuiop", "asdfghjkl", "zxcvbnm", "1234567890"];

export const DEFAULT_POLICY = { min_length: 12, passphrase_length: 16, max_length: 128, common: [] };

const leet = (s) => [...s].map((c) => LEET[c] ?? c).join("");
const lettersOnly = (s) => s.replace(/[^a-z]/g, "");

function classes(pw) {
  return [/[a-z]/, /[A-Z]/, /[0-9]/, /[^A-Za-z0-9]/].filter((r) => r.test(pw)).length;
}

function hasRun(pw, n = 4) {
  const s = pw.toLowerCase();
  for (let i = 0; i + n <= s.length; i++) {
    const c = s.slice(i, i + n);
    if (new Set(c).size === 1) return true;
    const steps = new Set([...c].slice(1).map((ch, j) => ch.charCodeAt(0) - c.charCodeAt(j)));
    if (steps.size === 1 && (steps.has(1) || steps.has(-1)) && /^[a-z0-9]+$/.test(c)) return true;
    if (ROWS.some((r) => r.includes(c) || [...r].reverse().join("").includes(c))) return true;
  }
  return false;
}

function isCommon(pw, common) {
  const words = new Set(common);
  const trimmed = pw.toLowerCase().replace(/^[\W\d_]+|[\W\d_]+$/g, "");
  const core = lettersOnly(leet(trimmed));
  if (core.length < 4 || words.has(core) || common.some((w) => core === w + w)) return true;
  const whole = lettersOnly(leet(pw.toLowerCase()));
  return common.some((w) => w.length >= 5 && whole.includes(w));
}

export function passwordChecks(pw, email, policy = DEFAULT_POLICY) {
  const local = (email.split("@")[0] || "").toLowerCase();
  const longPhrase = pw.length >= policy.passphrase_length;
  return [
    { label: `At least ${policy.min_length} characters`, ok: pw.length >= policy.min_length && pw.length <= policy.max_length },
    { label: `Mix of upper and lower case, numbers or symbols — or ${policy.passphrase_length}+ characters`,
      ok: classes(pw) >= (longPhrase ? 2 : 3) },
    { label: "Not a common or easily guessed password", ok: pw.length > 0 && !isCommon(pw, policy.common) },
    { label: "No runs like 1234, abcd, qwer or aaaa", ok: pw.length > 0 && !hasRun(pw) },
    { label: "Doesn't contain your email name", ok: pw.length > 0 && !(local.length >= 4 && pw.toLowerCase().includes(local)) },
  ];
}

// 0-4 for the meter: stays low until every rule passes, then length and variety add up
export function passwordStrength(pw, email, policy = DEFAULT_POLICY) {
  if (!passwordChecks(pw, email, policy).every((c) => c.ok)) return pw.length >= 8 ? 1 : 0;
  return Math.min(4, 2 + (pw.length >= 16 ? 1 : 0) + (classes(pw) === 4 ? 1 : 0));
}

// --- email --------------------------------------------------------------- //

const EMAIL = /^[^\s@]+@[^\s@]+\.[A-Za-z]{2,}$/;
const DOMAIN_TYPOS = {
  "gmial.com": "gmail.com", "gmai.com": "gmail.com", "gamil.com": "gmail.com", "gmail.co": "gmail.com",
  "gmail.con": "gmail.com", "gmail.cm": "gmail.com", "gmaill.com": "gmail.com", "gnail.com": "gmail.com",
  "yahooo.com": "yahoo.com", "yaho.com": "yahoo.com", "yahoo.co": "yahoo.com", "yahoo.con": "yahoo.com",
  "hotmial.com": "hotmail.com", "hotmai.com": "hotmail.com", "hotmail.co": "hotmail.com",
  "outlok.com": "outlook.com", "outlook.co": "outlook.com", "rediffmial.com": "rediffmail.com",
  "redifmail.com": "rediffmail.com", "icloud.co": "icloud.com",
};

// { error } for an invalid address, { suggestion } for a likely typo, {} when fine
export function emailCheck(email) {
  const e = email.trim();
  if (!e) return { error: "Enter your email address." };
  if (!EMAIL.test(e)) return { error: "That doesn't look like an email address (e.g. you@example.com)." };
  const [local, domain] = e.split("@");
  const fix = DOMAIN_TYPOS[domain.toLowerCase()];
  return fix ? { suggestion: `${local}@${fix}` } : {};
}
