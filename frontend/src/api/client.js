import axios from "axios";

// In production (Vercel), VITE_API_URL = "https://your-backend.up.railway.app"
// In local dev, leave VITE_API_URL unset — Vite proxies /api → localhost:8000
const BASE = import.meta.env.VITE_API_URL || "/api";

const api = axios.create({ baseURL: BASE });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export default api;

// Helper for plain <a href> links that go directly to the backend (e.g. OAuth)
// Local dev:   backendUrl("/auth/google/login") → "/api/auth/google/login" (Vite proxies it)
// Production:  backendUrl("/auth/google/login") → "https://railway-url.app/auth/google/login"
export function backendUrl(path) {
  return import.meta.env.VITE_API_URL
    ? `${import.meta.env.VITE_API_URL}${path}`
    : `/api${path}`;
}
