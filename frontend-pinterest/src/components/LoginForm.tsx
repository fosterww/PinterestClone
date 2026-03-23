import { useState } from "react";
import { useAuth } from "../context/AuthContext";

type Mode = "login" | "register";

export function LoginForm() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<Mode>("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.SyntheticEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      if (mode === "login") {
        await login(username, password);
      } else {
        await register({ id: "", username, email, password } as any);
        await login(username, password);
      }
    } catch (err: any) {
      const msg =
        err.response?.data?.detail ?? (mode === "login" ? "Invalid credentials" : "Registration failed");
      setError(typeof msg === "string" ? msg : JSON.stringify(msg));
    } finally {
      setLoading(false);
    }
  };

  const isLogin = mode === "login";

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo">
          <div className="auth-logo-icon">P</div>
        </div>
        <h2>{isLogin ? "Welcome back" : "Create account"}</h2>
        <p>{isLogin ? "Log in to see your pins" : "Join to discover great ideas"}</p>

        {error && <div className="form-error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              className="form-input"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              required
            />
          </div>

          {!isLogin && (
            <div className="form-group">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                className="form-input"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required={!isLogin}
              />
            </div>
          )}

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              className="form-input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={isLogin ? "current-password" : "new-password"}
              required
            />
          </div>

          <button
            type="submit"
            className="btn btn-red"
            disabled={loading}
            style={{ width: "100%", justifyContent: "center", marginTop: "8px", height: "48px", fontSize: "16px" }}
          >
            {loading ? (isLogin ? "Logging in…" : "Registering…") : isLogin ? "Log in" : "Register"}
          </button>
        </form>

        <div className="auth-toggle">
          {isLogin ? "Don't have an account?" : "Already have an account?"}
          <button onClick={() => { setMode(isLogin ? "register" : "login"); setError(""); }}>
            {isLogin ? "Register" : "Log in"}
          </button>
        </div>
      </div>
    </div>
  );
}
