import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const nav = useNavigate();

  function handleLogout() {
    logout();
    nav("/login");
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <h2>FMR</h2>
        <NavLink to="/generate" className={({ isActive }) => isActive ? "active" : ""}>
          Generate Proposal
        </NavLink>
        <NavLink to="/my-proposals" className={({ isActive }) => isActive ? "active" : ""}>
          My Proposals
        </NavLink>
        <NavLink to="/profile" className={({ isActive }) => isActive ? "active" : ""}>
          My Profile
        </NavLink>
        {user?.role === "admin" && (
          <NavLink to="/admin" className={({ isActive }) => isActive ? "active" : ""}>
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
