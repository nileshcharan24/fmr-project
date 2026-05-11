import { useState, useEffect } from "react";
import api from "../api/client";

// ── Users tab ─────────────────────────────────────────────────────────────────
function UsersTab() {
  const [users, setUsers] = useState([]);
  const [pending, setPending] = useState([]);
  const [form, setForm] = useState({ username: "", password: "", role: "user" });
  const [resetPw, setResetPw] = useState({}); // { [userId]: newPassword }
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");

  function load() {
    api.get("/admin/users").then((r) => setUsers(r.data));
    api.get("/admin/users/pending").then((r) => setPending(r.data));
  }
  useEffect(load, []);

  async function createUser(e) {
    e.preventDefault();
    setError(""); setMsg("");
    try {
      await api.post("/admin/users", form);
      setMsg(`User "${form.username}" created.`);
      setForm({ username: "", password: "", role: "user" });
      load();
    } catch (err) { setError(err.response?.data?.detail || "Failed"); }
  }

  async function deleteUser(id, name) {
    if (!confirm(`Delete user "${name}"?`)) return;
    await api.delete(`/admin/users/${id}`);
    load();
  }

  async function resetLimit(id) {
    await api.post(`/admin/users/${id}/reset-rate-limit`);
    setMsg("Rate limit reset.");
    setTimeout(() => setMsg(""), 2000);
  }

  async function approve(id) {
    await api.post(`/admin/users/${id}/approve`);
    setMsg("User approved.");
    setTimeout(() => setMsg(""), 2000);
    load();
  }

  async function reject(id) {
    await api.post(`/admin/users/${id}/reject`);
    setMsg("User rejected.");
    setTimeout(() => setMsg(""), 2000);
    load();
  }

  async function resetPassword(id) {
    const pw = resetPw[id];
    if (!pw || pw.length < 6) { setError("Password must be at least 6 characters."); return; }
    setError("");
    try {
      await api.put(`/admin/users/${id}/password`, { password: pw });
      setResetPw((p) => ({ ...p, [id]: "" }));
      setMsg("Password updated.");
      setTimeout(() => setMsg(""), 2000);
    } catch (err) { setError(err.response?.data?.detail || "Failed"); }
  }

  const statusTag = (s) => {
    const color = s === "active" ? "done" : s === "rejected" ? "error" : "pending";
    return <span className={`tag tag-${color}`}>{s}</span>;
  };

  return (
    <div>
      {pending.length > 0 && (
        <div className="card" style={{ borderLeft: "3px solid #f59e0b" }}>
          <div className="section-title">Pending Access Requests ({pending.length})</div>
          <table>
            <thead><tr><th>Username</th><th>Requested</th><th>Actions</th></tr></thead>
            <tbody>
              {pending.map((u) => (
                <tr key={u.id}>
                  <td>{u.username}</td>
                  <td>{u.created_at?.slice(0, 10)}</td>
                  <td style={{ display: "flex", gap: 6 }}>
                    <button className="btn btn-primary btn-sm" onClick={() => approve(u.id)}>Approve</button>
                    <button className="btn btn-danger btn-sm" onClick={() => reject(u.id)}>Reject</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="card">
        <div className="section-title">Create User</div>
        {error && <div className="alert alert-error">{error}</div>}
        {msg   && <div className="alert alert-success">{msg}</div>}
        <form onSubmit={createUser}>
          <div className="form-row">
            <div className="form-group">
              <label>Username</label>
              <input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required />
            </div>
            <div className="form-group">
              <label>Password</label>
              <input value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
            </div>
          </div>
          <div className="form-group">
            <label>Role</label>
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              <option value="user">User</option>
              <option value="cohead">Co-Head</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <button className="btn btn-primary btn-sm" type="submit">Create</button>
        </form>
      </div>

      <div className="card">
        <div className="section-title">All Users</div>
        <table>
          <thead><tr><th>Username</th><th>Role</th><th>Status</th><th>Created</th><th>Actions</th></tr></thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>{u.username}</td>
                <td><span className="tag tag-pending">{u.role}</span></td>
                <td>{statusTag(u.status)}</td>
                <td>{u.created_at?.slice(0, 10)}</td>
                <td>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    {u.status === "pending" && <button className="btn btn-primary btn-sm" onClick={() => approve(u.id)}>Approve</button>}
                    {u.status === "pending" && <button className="btn btn-danger btn-sm" onClick={() => reject(u.id)}>Reject</button>}
                    {u.status === "active"  && <button className="btn btn-secondary btn-sm" onClick={() => reject(u.id)}>Revoke</button>}
                    {u.status === "rejected" && <button className="btn btn-secondary btn-sm" onClick={() => approve(u.id)}>Re-approve</button>}
                    <button className="btn btn-secondary btn-sm" onClick={() => resetLimit(u.id)}>Reset limit</button>
                    <button className="btn btn-danger btn-sm" onClick={() => deleteUser(u.id, u.username)}>Delete</button>
                  </div>
                  <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
                    <input
                      type="password"
                      placeholder="New password"
                      style={{ fontSize: 12, padding: "3px 6px", borderRadius: 4, border: "1px solid #d4d4d8", width: 130 }}
                      value={resetPw[u.id] || ""}
                      onChange={(e) => setResetPw((p) => ({ ...p, [u.id]: e.target.value }))}
                    />
                    <button className="btn btn-secondary btn-sm" onClick={() => resetPassword(u.id)}>Set pw</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Proposals tab ─────────────────────────────────────────────────────────────
function ProposalsTab() {
  const [proposals, setProposals] = useState([]);
  const [expanded, setExpanded] = useState(null);
  useEffect(() => { api.get("/admin/proposals").then((r) => setProposals(r.data)); }, []);

  function statusTag(status) {
    const cls = status === "done" ? "done" : status === "error" ? "error" : "pending";
    return <span className={`tag tag-${cls}`}>{status}</span>;
  }

  return (
    <div className="card">
      <div className="section-title">All Proposals</div>
      {proposals.length === 0 ? <p style={{ color: "#71717a" }}>None yet.</p> : (
        <table>
          <thead>
            <tr><th>User</th><th>Company</th><th>Tier</th><th>Status</th><th>Date</th></tr>
          </thead>
          <tbody>
            {proposals.map((p) => (
              <>
                <tr key={p.id}
                  style={{ cursor: p.error_message ? "pointer" : "default" }}
                  onClick={() => p.error_message && setExpanded(expanded === p.id ? null : p.id)}
                  title={p.error_message ? "Click to see error details" : undefined}
                >
                  <td>{p.username}</td>
                  <td>{p.company_name}</td>
                  <td>Tier {p.tier}</td>
                  <td>{statusTag(p.status)}</td>
                  <td>{p.created_at?.slice(0, 16).replace("T", " ")}</td>
                </tr>
                {expanded === p.id && p.error_message && (
                  <tr key={`err-${p.id}`}>
                    <td colSpan={5}>
                      <div className="alert alert-error" style={{ margin: "4px 0", fontSize: 12, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                        <strong>Error:</strong> {p.error_message}
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ── Clusters tab ──────────────────────────────────────────────────────────────
function ClustersTab() {
  const [clusters, setClusters] = useState({});
  const [editing, setEditing] = useState(null);
  const [editVal, setEditVal] = useState("");
  const [msg, setMsg] = useState("");

  function load() { api.get("/admin/resources/clusters").then((r) => setClusters(r.data)); }
  useEffect(load, []);

  async function save() {
    const updated = { ...clusters, [editing]: editVal };
    await api.put("/admin/resources/clusters", updated);
    setClusters(updated);
    setEditing(null);
    setMsg("Saved.");
    setTimeout(() => setMsg(""), 2000);
  }

  function startEdit(name) { setEditing(name); setEditVal(clusters[name] || ""); }

  return (
    <div className="card">
      <div className="section-title">Cluster Descriptions</div>
      {msg && <div className="alert alert-success">{msg}</div>}
      {Object.keys(clusters).length === 0 && <p style={{ color: "#71717a" }}>No clusters configured.</p>}
      {Object.entries(clusters).map(([name, desc]) => (
        <div key={name} style={{ marginBottom: 14, borderBottom: "1px solid #f4f4f5", paddingBottom: 14 }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>{name}</div>
          {editing === name ? (
            <>
              <textarea rows={3} style={{ width: "100%", fontSize: 13, padding: 6, borderRadius: 5, border: "1px solid #d4d4d8" }}
                value={editVal} onChange={(e) => setEditVal(e.target.value)} />
              <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
                <button className="btn btn-primary btn-sm" onClick={save}>Save</button>
                <button className="btn btn-secondary btn-sm" onClick={() => setEditing(null)}>Cancel</button>
              </div>
            </>
          ) : (
            <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
              <div style={{ flex: 1, fontSize: 13, color: "#52525b" }}>{desc || <em style={{ color: "#a1a1aa" }}>No description</em>}</div>
              <button className="btn btn-secondary btn-sm" onClick={() => startEdit(name)}>Edit</button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Resources tab ─────────────────────────────────────────────────────────────
function ResourcesTab() {
  const [resources, setResources] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState("");

  function load() { api.get("/admin/resources").then((r) => setResources(r.data)); }
  useEffect(load, []);

  async function upload(e) {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true);
    const form = new FormData();
    form.append("file", file);
    try {
      await api.post("/admin/resources", form);
      setMsg(`Uploaded "${file.name}".`);
      load();
    } catch (err) { setMsg(err.response?.data?.detail || "Upload failed"); }
    finally { setUploading(false); e.target.value = ""; }
  }

  async function del(filename) {
    if (!confirm(`Delete "${filename}"?`)) return;
    await api.delete(`/admin/resources/${encodeURIComponent(filename)}`);
    load();
  }

  return (
    <div className="card">
      <div className="section-title">Resource Files</div>
      {msg && <div className="alert alert-info" style={{ marginBottom: 10 }}>{msg}</div>}
      <div style={{ marginBottom: 14 }}>
        <label className="btn btn-secondary btn-sm" style={{ display: "inline-block" }}>
          {uploading ? "Uploading…" : "Upload file"}
          <input type="file" style={{ display: "none" }} onChange={upload} accept=".docx,.pptx,.json,.pdf,.png,.jpg,.jpeg" />
        </label>
      </div>
      <table>
        <thead><tr><th>File</th><th>Size</th><th>Modified</th><th></th></tr></thead>
        <tbody>
          {resources.map((r) => (
            <tr key={r.filename}>
              <td style={{ wordBreak: "break-all" }}>{r.path || r.filename}</td>
              <td>{r.size_kb?.toFixed(1)} KB</td>
              <td>{new Date(r.modified * 1000).toLocaleDateString()}</td>
              <td><button className="btn btn-danger btn-sm" onClick={() => del(r.filename)}>Delete</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Main Admin page ───────────────────────────────────────────────────────────
export default function Admin() {
  const [tab, setTab] = useState("users");
  const tabs = [
    { key: "users",     label: "Users" },
    { key: "proposals", label: "Proposals" },
    { key: "clusters",  label: "Clusters" },
    { key: "resources", label: "Resources" },
  ];

  return (
    <div>
      <div className="page-title">Admin Panel</div>
      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        {tabs.map((t) => (
          <button
            key={t.key}
            className={`btn ${tab === t.key ? "btn-primary" : "btn-secondary"} btn-sm`}
            onClick={() => setTab(t.key)}
          >{t.label}</button>
        ))}
      </div>
      {tab === "users"     && <UsersTab />}
      {tab === "proposals" && <ProposalsTab />}
      {tab === "clusters"  && <ClustersTab />}
      {tab === "resources" && <ResourcesTab />}
    </div>
  );
}
