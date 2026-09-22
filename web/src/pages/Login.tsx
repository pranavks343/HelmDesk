import { FormEvent, useState } from "react";
import { LockKeyhole, PlaneTakeoff, UserPlus } from "lucide-react";
import { api, type Role } from "../api/client";
import type { Session } from "../App";

type Props = {
  onLogin: (session: Session) => void;
};

export default function Login({ onLogin }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("demo@example.com");
  const [password, setPassword] = useState("password123");
  const [role, setRole] = useState<Role>("customer");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      if (mode === "register") {
        await api.register(email, password, role);
      }
      const tokens = await api.login(email, password);
      onLogin({ ...tokens, email });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-panel">
        <div className="brand-mark">
          <PlaneTakeoff aria-hidden="true" size={24} />
        </div>
        <div>
          <p className="eyebrow">SupportPilot</p>
          <h1>Agent-ready ticket desk</h1>
        </div>
        <div className="segmented" aria-label="Authentication mode">
          <button className={mode === "login" ? "active" : ""} onClick={() => setMode("login")} type="button">
            <LockKeyhole size={16} aria-hidden="true" />
            Sign in
          </button>
          <button
            className={mode === "register" ? "active" : ""}
            onClick={() => setMode("register")}
            type="button"
          >
            <UserPlus size={16} aria-hidden="true" />
            Register
          </button>
        </div>
        <form className="stack" onSubmit={submit}>
          <label>
            Email
            <input autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} />
          </label>
          <label>
            Password
            <input
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          {mode === "register" ? (
            <label>
              Role
              <select value={role} onChange={(event) => setRole(event.target.value as Role)}>
                <option value="customer">Customer</option>
                <option value="agent">Agent</option>
                <option value="admin">Admin</option>
              </select>
            </label>
          ) : null}
          {error ? <p className="error-text">{error}</p> : null}
          <button className="primary-action" disabled={loading} type="submit">
            {loading ? "Working..." : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>
      </section>
    </main>
  );
}
