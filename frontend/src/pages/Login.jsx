import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import api, { backendUrl } from "../api/client";
import { useAuth } from "../AuthContext";

function profileComplete(data) {
  return data?.full_name?.trim() && data?.designation?.trim() && data?.email?.trim();
}

const OAUTH_ERRORS = {
  oauth_cancelled:      "Google sign-in was cancelled.",
  not_configured:       "Google OAuth is not configured on this server.",
  token_exchange_failed:"Failed to complete Google sign-in. Please try again.",
  userinfo_failed:      "Could not retrieve your Google account info.",
  domain_not_allowed:   "Only .nitt@gmail.com accounts are allowed.",
  pending_approval:     "Account created! Your access is pending admin approval. You'll be notified once approved.",
  still_pending:        "Your account is still pending admin approval.",
  rejected:             "Your access request was rejected. Contact the admin.",
};

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ username: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Handle OAuth redirect back — token on success, error param on failure
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get("token");
    const oauthError = params.get("error");

    if (token) {
      const username = params.get("username") || "";
      const role = params.get("role") || "user";
      login(token, { username, role });
      api.get("/auth/me").then((r) => {
        nav(profileComplete(r.data) ? "/generate" : "/profile", { replace: true });
      }).catch(() => nav("/generate", { replace: true }));
      return;
    }

    if (oauthError) {
      setError(OAUTH_ERRORS[oauthError] || "Google sign-in failed.");
      window.history.replaceState({}, "", "/login");
    }
  }, []);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await api.post("/auth/login", { username: form.username, password: form.password });
      login(res.data.token, { username: res.data.username, role: res.data.role });
      const me = await api.get("/auth/me");
      nav(profileComplete(me.data) ? "/generate" : "/profile");
    } catch (err) {
      if (err.response) {
        setError(err.response.data?.detail || `Server error (${err.response.status})`);
      } else {
        setError(`Cannot reach backend — check VITE_API_URL. (${err.message})`);
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-wrap">
      <div className="login-card">
        <h1>FMR Platform</h1>
        <p className="sub">Festember Media &amp; Reach — Proposal Generator</p>

        {error && <div className="alert alert-error">{error}</div>}

        {/* Google Sign-in — for all team members */}
        <a
          href={backendUrl("/auth/google/login")}
          style={{
            display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
            width: "100%", padding: "9px 0", border: "1px solid #d4d4d8",
            borderRadius: 6, background: "#fff", color: "#3f3f46",
            fontSize: 14, fontWeight: 500, textDecoration: "none", boxSizing: "border-box",
          }}
        >
          <svg width="18" height="18" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg">
            <g fill="none" fillRule="evenodd">
              <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/>
              <path d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#34A853"/>
              <path d="M3.964 10.706A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.706V4.962H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.038l3.007-2.332z" fill="#FBBC05"/>
              <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.962L3.964 7.294C4.672 5.163 6.656 3.58 9 3.58z" fill="#EA4335"/>
            </g>
          </svg>
          Sign in with Google
        </a>
        <p style={{ fontSize: 11, color: "#a1a1aa", textAlign: "center", marginTop: 8, marginBottom: 0 }}>
          Only .nitt@gmail.com accounts are permitted.
        </p>

        {/* Divider */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, margin: "16px 0 14px" }}>
          <div style={{ flex: 1, height: 1, background: "#e4e4e7" }} />
          <span style={{ fontSize: 11, color: "#a1a1aa" }}>admin only</span>
          <div style={{ flex: 1, height: 1, background: "#e4e4e7" }} />
        </div>

        {/* Username/password — for admin only */}
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Username</label>
            <input
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              required autoFocus
            />
          </div>
          <div className="form-group">
            <label>Password</label>
            <input
              type="password"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              required
            />
          </div>
          <button className="btn btn-secondary" style={{ width: "100%", marginTop: 8 }} disabled={loading}>
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
