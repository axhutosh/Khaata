import { useEffect, useState } from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { api } from "./api";
import Shell from "./components/Shell";
import Login from "./pages/Login";
import Upload from "./pages/Upload";
import Dashboard from "./pages/Dashboard";
import Transactions from "./pages/Transactions";
import Subscriptions from "./pages/Subscriptions";
import Budgets from "./pages/Budgets";

function useAuth() {
  const [state, setState] = useState({ loading: true, user: null });
  const loc = useLocation();
  useEffect(() => {
    api.me().then((u) => setState({ loading: false, user: u }))
      .catch(() => setState({ loading: false, user: null }));
  }, [loc.pathname]);
  return state;
}

function Private({ children, bare }) {
  const { loading, user } = useAuth();
  if (loading) return <p style={{ padding: 40 }}>Loading…</p>;
  if (!user) return <Navigate to="/login" replace />;
  return bare ? children : <Shell>{children}</Shell>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Login />} />
      <Route path="/upload" element={<Private bare><Upload /></Private>} />
      <Route path="/" element={<Private><Dashboard /></Private>} />
      <Route path="/transactions" element={<Private><Transactions /></Private>} />
      <Route path="/subscriptions" element={<Private><Subscriptions /></Private>} />
      <Route path="/budgets" element={<Private><Budgets /></Private>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
