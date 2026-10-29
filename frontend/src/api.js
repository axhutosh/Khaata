// Thin API client. All calls go through the Vite proxy at /api -> FastAPI :8000.
const BASE = "/api";

async function req(path, opts = {}) {
  const res = await fetch(BASE + path, {
    credentials: "include",
    headers: opts.body && !(opts.body instanceof FormData)
      ? { "Content-Type": "application/json" }
      : undefined,
    ...opts,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Request failed (${res.status})`);
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  me: () => req("/auth/me"),
  login: (email, password) =>
    req("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  logout: () => req("/auth/logout", { method: "POST" }),

  preview: (file, password) => {
    const fd = new FormData();
    fd.append("file", file);
    if (password) fd.append("password", password);
    return req("/upload/preview", { method: "POST", body: fd });
  },
  commit: (token, corrections) =>
    req("/upload/commit", { method: "POST", body: JSON.stringify({ token, corrections }) }),
  uploads: () => req("/uploads"),
  deleteUpload: (id) => req(`/uploads/${id}`, { method: "DELETE" }),

  overview: (period = "month") => req(`/insights/overview?period=${period}`),
  recurring: () => req("/insights/recurring"),
  transactions: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return req(`/transactions${qs ? "?" + qs : ""}`);
  },
  recategorize: (id, category) =>
    req(`/transactions/${id}/category`, {
      method: "PATCH",
      body: JSON.stringify({ category, apply_to_similar: true }),
    }),
  budgets: (month) => req(`/budgets${month ? "?month=" + month : ""}`),
  setBudget: (category, monthly_limit) =>
    req("/budgets", { method: "PUT", body: JSON.stringify({ category, monthly_limit }) }),
};

export const inr = (n) =>
  "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });

// exact to the paisa, for reconciliation figures
export const inrExact = (n) =>
  "₹" + Number(n || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const monthLabel = (ym) =>
  new Date(ym + "-01T00:00:00").toLocaleString("en-IN", { month: "long", year: "numeric" });
