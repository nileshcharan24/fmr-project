import { useState, useEffect } from "react";
import api from "../api/client";

const PHONE_RE = /^\+\d{1,4} \d{5} \d{5}$/;

export default function Profile() {
  const [form, setForm] = useState({ full_name: "", designation: "", phone: "", email: "" });
  const [emailLocked, setEmailLocked] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api.get("/auth/me").then((r) => {
      const d = r.data;
      setForm({
        full_name:   d.full_name   || "",
        designation: d.designation || "",
        phone:       d.phone       || "",
        email:       d.email       || "",
      });
      setEmailLocked(!!d.email);
    }).finally(() => setLoading(false));
  }, []);

  function validate() {
    if (!form.full_name.trim()) return "Full name is required.";
    if (!form.designation.trim()) return "Designation is required.";
    if (!form.email.trim()) return "Email is required.";
    if (form.phone && !PHONE_RE.test(form.phone))
      return "Phone must be in format: +91 98765 43210 (+<country code> <5 digits> <5 digits>)";
    return null;
  }

  async function save(e) {
    e.preventDefault();
    setMsg(""); setError("");
    const err = validate();
    if (err) { setError(err); return; }
    setSaving(true);
    try {
      await api.put("/auth/profile", form);
      setMsg("Profile saved.");
      setEmailLocked(!!form.email);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to save profile.");
    } finally {
      setSaving(false);
    }
  }

  const isComplete = form.full_name.trim() && form.designation.trim() && form.email.trim();

  if (loading) return <div>Loading…</div>;

  return (
    <div>
      <div className="page-title">My Profile</div>
      <div className="card" style={{ maxWidth: 520 }}>
        <p style={{ fontSize: 13, color: "#52525b", marginBottom: 18 }}>
          This information appears in the contact slide of every proposal you generate.
          All fields except phone are required before you can generate proposals.
        </p>
        {!isComplete && (
          <div className="alert alert-error" style={{ marginBottom: 14 }}>
            Complete your profile before generating proposals.
          </div>
        )}
        {msg   && <div className="alert alert-success">{msg}</div>}
        {error && <div className="alert alert-error">{error}</div>}
        <form onSubmit={save}>
          <div className="form-group">
            <label>Full Name <span style={{ color: "#ef4444" }}>*</span></label>
            <input
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              required
            />
          </div>
          <div className="form-group">
            <label>Designation <span style={{ color: "#ef4444" }}>*</span></label>
            <input
              value={form.designation}
              onChange={(e) => setForm({ ...form, designation: e.target.value })}
              required
            />
          </div>
          <div className="form-group">
            <label>Phone</label>
            <input
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
              placeholder="+91 98765 43210"
            />
            <div className="form-hint">Format: +&lt;country code&gt; &lt;5 digits&gt; &lt;5 digits&gt;</div>
          </div>
          <div className="form-group">
            <label>
              Email <span style={{ color: "#ef4444" }}>*</span>
              {emailLocked && (
                <span style={{ marginLeft: 8, fontSize: 11, color: "#71717a", fontWeight: 400 }}>
                  (locked — contact admin to change)
                </span>
              )}
            </label>
            <input
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              disabled={emailLocked}
              style={emailLocked ? { background: "#f4f4f5", color: "#71717a" } : {}}
              required
            />
          </div>
          <button className="btn btn-primary" type="submit" disabled={saving}>
            {saving ? "Saving…" : "Save Profile"}
          </button>
        </form>
      </div>
    </div>
  );
}
