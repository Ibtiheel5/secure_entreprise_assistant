import { FormEvent, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { errMsg } from "../api";
import { Err } from "../components/Layout";

export default function Login() {
  const { login, user } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState(""); const [password, setPassword] = useState("");
  const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/" replace />;
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setError("");
    try { await login(email, password); nav("/"); } catch (x) { setError(errMsg(x)); } finally { setBusy(false); }
  };
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50">
      <form onSubmit={submit} className="card w-full max-w-sm space-y-4">
        <div><div className="text-xs uppercase tracking-widest text-gold-500">Enterprise</div>
          <h1 className="text-lg font-semibold text-navy-900">Knowledge Assistant</h1></div>
        <Err msg={error} />
        <label className="block text-sm">Email<input className="input mt-1" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
        <label className="block text-sm">Password<input className="input mt-1" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
        <button className="btn w-full justify-center" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
      </form>
    </div>
  );
}
