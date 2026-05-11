import { useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  function handleLogout() {
    logout();
    nav("/login");
  }

  function close() {
    setSidebarOpen(false);
  }

  return (
    <div className="layout">
      <button
        className="sidebar-toggle"
        onClick={() => setSidebarOpen(o => !o)}
        aria-label="Toggle sidebar"
      >
        &#9776;
      </button>
      {sidebarOpen && (
        <div className="sidebar-overlay" onClick={close} />
      )}
      <aside className={`sidebar${sidebarOpen ? " sidebar-open" : ""}`}>
        <h2>FMR</h2>
        <NavLink to="/generate" className={({ isActive }) => isActive ? "active" : ""} onClick={close}>
          Generate Proposal
        </NavLink>
        <NavLink to="/my-proposals" className={({ isActive }) => isActive ? "active" : ""} onClick={close}>
          My Proposals
        </NavLink>
        <NavLink to="/profile" className={({ isActive }) => isActive ? "active" : ""} onClick={close}>
          My Profile
        </NavLink>
        {user?.role === "admin" && (
          <NavLink to="/admin" className={({ isActive }) => isActive ? "active" : ""} onClick={close}>
            Admin
          </NavLink>
        )}
        <div className="sidebar-footer">
          <div style={{ fontSize: 12, color: "#71717a", marginBottom: 8 }}>{user?.username}</div>
          <button className="nav-link" onClick={handleLogout} style={{ paddingLeft: 0, color: "#a1a1aa" }}>
            Sign out
          </button>
        </div>
      </aside>
      <main className="main-content">{children}</main>
    </div>
  );
}
