import { useState, useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import api from "../api/client";

const ALL_CLUSTERS = [
  "Music", "Dance", "Dramatics", "Arts",
  "English Lits", "Tamil Lits", "Hindi Lits", "Telugu Lits",
  "Photography", "Fashion", "Proshows",
];

const OUTREACH_EVENTS = ["Gigahertz", "Festember Football League", "Rolling Reels Film Festival"];
const OUTREACH_CITIES = ["Bangalore", "Chennai", "Pondicherry", "Kochi", "Hyderabad"];

const TIER_CLUSTER_REC = { 1: "3–5 recommended", 2: "2–3 recommended", 3: "1 recommended" };
const TIER_BANNER_REC  = { 1: "3–4 total (max 6)", 2: "2 total (max 6)", 3: "1 recommended" };

const OPTIONAL_SLIDES = [
  { key: "include_pronite",           label: "Pronite Partnership",   hint: "Sponsorship for Festember's pronite concerts" },
  { key: "include_brand_engagement",  label: "Brand Engagement",      hint: "Company's brand activation on the informals stage" },
  { key: "include_outreach",          label: "Outreach",              hint: "Pre-fest outreach events (Gigahertz, FFL, etc.)" },
  { key: "include_csr",               label: "CSR",                   hint: "Corporate Social Responsibility slide" },
  { key: "include_cluster",           label: "Cluster Association",   hint: "Associate with specific clusters (Music, Dance…)" },
  { key: "include_event_association", label: "Event Association",     hint: "Associate with one specific event instead of clusters" },
];

const TIER_DEFAULTS = {
  1: { include_pronite: true,  include_brand_engagement: true,  include_outreach: true,  include_csr: true,  include_cluster: true, include_event_association: false },
  2: { include_pronite: false, include_brand_engagement: false, include_outreach: true,  include_csr: false, include_cluster: true, include_event_association: false },
  3: { include_pronite: false, include_brand_engagement: false, include_outreach: true,  include_csr: false, include_cluster: true, include_event_association: false },
};

const PROGRESS_MESSAGES = [
  "Analysing company details…",
  "Drafting deliverables…",
  "Building PPT slides…",
  "Inserting logo and cluster slides…",
  "Generating cover letter…",
  "Finalising proposal…",
];

function UsageBar({ usage }) {
  if (!usage) return null;
  const resetsDate = new Date(usage.resets_on + "T00:00:00");
  const resetsLabel = resetsDate.toLocaleDateString("en-GB", {
    weekday: "long", day: "numeric", month: "short",
  });
  return (
    <div className="alert alert-info" style={{ marginBottom: 20 }}>
      Proposals this week: <strong>{usage.used} / {usage.limit}</strong> — resets {resetsLabel}
    </div>
  );
}

// ── Step 1 ────────────────────────────────────────────────────────────────────
function Step1({ onDraftJobStarted }) {
  const [form, setForm] = useState({
    company_name: "",
    tier: 1,
    clusters: [],
    banner_count: 3,
    outreach_event: "Gigahertz",
    outreach_city: "Bangalore",
    extra_context: "",
    logo_path: "",
    ...TIER_DEFAULTS[1],
  });
  const [slideDetails, setSlideDetails] = useState({});
  const [loading, setLoading] = useState(false);
  const [logoLoading, setLogoLoading] = useState(false);
  const [error, setError] = useState("");
  const [profileMissing, setProfileMissing] = useState(false);
  const [logoName, setLogoName] = useState("");
  const fileInputRef = useRef(null);

  useEffect(() => {
    api.get("/auth/me").then((r) => {
      const p = r.data;
      if (!p.full_name?.trim() || !p.designation?.trim() || !p.email?.trim()) setProfileMissing(true);
    });
  }, []);

  function setField(k, v) {
    setForm((f) => {
      const next = { ...f, [k]: v };
      if (k === "tier") Object.assign(next, TIER_DEFAULTS[v]);
      return next;
    });
  }

  function toggleCluster(c) {
    setForm((f) => {
      const has = f.clusters.includes(c);
      return { ...f, clusters: has ? f.clusters.filter((x) => x !== c) : [...f.clusters, c] };
    });
  }

  function toggleSlide(key) {
    setForm((f) => {
      const next = { ...f, [key]: !f[key] };
      if (key === "include_event_association" && next.include_event_association) next.include_cluster = false;
      if (key === "include_cluster" && next.include_cluster) next.include_event_association = false;
      return next;
    });
  }

  async function handleLogoUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setLogoLoading(true);
    setError("");
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await api.post("/proposals/upload-logo", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setField("logo_path", res.data.logo_path);
      setLogoName(file.name);
    } catch (err) {
      setError("Logo upload failed: " + (err.response?.data?.detail || err.message));
    } finally {
      setLogoLoading(false);
    }
  }

  async function submit(e) {
    e.preventDefault();
    setError("");
    if (!form.clusters.length) { setError("Select at least one cluster."); return; }
    setLoading(true);

    const slideCtxLines = Object.entries(slideDetails)
      .filter(([, v]) => v.trim())
      .map(([k, v]) => {
        const slide = OPTIONAL_SLIDES.find((s) => s.key === k);
        return `${slide?.label || k}: ${v}`;
      });
    const fullContext = [form.extra_context, ...slideCtxLines].filter(Boolean).join("\n\n");

    try {
      const res = await api.post("/proposals/draft", { ...form, extra_context: fullContext });
      // Backend now returns immediately with a draft_job_id to poll
      onDraftJobStarted(res.data.draft_job_id, form);
    } catch (err) {
      const d = err.response?.data?.detail;
      setError(typeof d === "string" ? d : Array.isArray(d) ? d.map(e => e.msg || JSON.stringify(e)).join("; ") : `Failed to start draft. (${err.message || "network error"})`)
    } finally {
      setLoading(false);
    }
  }

  const tier = form.tier;

  return (
    <form onSubmit={submit}>
      {error && <div className="alert alert-error">{error}</div>}
      {profileMissing && (
        <div className="alert alert-error">
          Your <Link to="/profile" style={{ textDecoration: "underline", fontWeight: 600 }}>profile</Link> is incomplete — fill in your name, designation, and email before you can generate proposals.
        </div>
      )}

      {/* Company */}
      <div className="card">
        <div className="section-title">Company Details</div>
        <div className="form-row">
          <div className="form-group">
            <label>Company Name</label>
            <input value={form.company_name} onChange={(e) => setField("company_name", e.target.value)} required />
          </div>
          <div className="form-group">
            <label>Tier</label>
            <select value={tier} onChange={(e) => setField("tier", Number(e.target.value))}>
              <option value={1}>Tier 1 (Premium)</option>
              <option value={2}>Tier 2</option>
              <option value={3}>Tier 3</option>
            </select>
          </div>
        </div>

        <div className="form-group">
          <label>Clusters <span style={{ fontWeight: 400, color: "#71717a" }}>— {TIER_CLUSTER_REC[tier]}</span></label>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 4 }}>
            {ALL_CLUSTERS.map((c) => (
              <button key={c} type="button"
                className={`chip ${form.clusters.includes(c) ? "chip-active" : ""}`}
                onClick={() => toggleCluster(c)}
              >{c}</button>
            ))}
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>
              Banners + standees
              <span style={{ fontWeight: 400, color: "#71717a" }}> (total, capped at 6 — {TIER_BANNER_REC[tier]})</span>
            </label>
            <input type="number" min={1} max={6} value={form.banner_count}
              onChange={(e) => setField("banner_count", Number(e.target.value))} />
          </div>
          <div className="form-group">
            <label>Outreach Event</label>
            <select value={form.outreach_event} onChange={(e) => setField("outreach_event", e.target.value)}
              disabled={!form.include_outreach}>
              {OUTREACH_EVENTS.map((ev) => <option key={ev} value={ev}>{ev}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>Outreach City</label>
            <select value={form.outreach_city} onChange={(e) => setField("outreach_city", e.target.value)}
              disabled={!form.include_outreach}>
              {OUTREACH_CITIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        </div>

        {/* Logo upload */}
        <div className="form-group">
          <label>Company Logo <span style={{ fontWeight: 400, color: "#71717a" }}>(optional — PNG or JPG, placed on slide 5)</span></label>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <button type="button" className="btn btn-secondary"
              onClick={() => fileInputRef.current?.click()}
              disabled={logoLoading}>
              {logoLoading ? "Uploading…" : "Upload Logo"}
            </button>
            <input ref={fileInputRef} type="file" accept="image/*" style={{ display: "none" }}
              onChange={handleLogoUpload} />
            {logoName && <span style={{ fontSize: 13, color: "#16a34a" }}>✓ {logoName}</span>}
          </div>
        </div>
      </div>

      {/* Optional slides */}
      <div className="card">
        <div className="section-title">Slides to Include</div>
        <p className="form-hint" style={{ marginBottom: 12 }}>
          Toggle which slides appear in the PPT. Defaults are set based on tier but you can override any of them.
          Note: Cluster Association and Event Association are mutually exclusive — enabling one disables the other.
        </p>
        {OPTIONAL_SLIDES.map(({ key, label, hint }) => (
          <div key={key} style={{ marginBottom: 14, paddingBottom: 14, borderBottom: "1px solid #f4f4f5" }}>
            <label style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer", marginBottom: 4 }}>
              <input type="checkbox" checked={!!form[key]} onChange={() => toggleSlide(key)} />
              <span style={{ fontWeight: 500 }}>{label}</span>
              <span style={{ fontWeight: 400, color: "#71717a", fontSize: 12 }}>{hint}</span>
            </label>
            {form[key] && key !== "include_event_association" && key !== "include_cluster" && (
              <textarea
                rows={2}
                placeholder={`Optional: extra details for the ${label} slide…`}
                style={{ width: "100%", marginTop: 4, fontSize: 13, padding: "6px 8px", borderRadius: 5, border: "1px solid #d4d4d8", resize: "vertical" }}
                value={slideDetails[key] || ""}
                onChange={(e) => setSlideDetails((d) => ({ ...d, [key]: e.target.value }))}
              />
            )}
          </div>
        ))}
      </div>

      {/* Extra context */}
      <div className="card">
        <div className="section-title">Additional Context <span style={{ fontWeight: 400, color: "#71717a" }}>(optional)</span></div>
        <div className="form-group">
          <textarea rows={3}
            placeholder="Tell the AI anything extra — product lines, target audience, past associations, specific requests…"
            value={form.extra_context}
            onChange={(e) => setField("extra_context", e.target.value)}
          />
        </div>
      </div>

      <button className="btn btn-primary" type="submit" disabled={loading || profileMissing}>
        {loading
          ? <><span className="spinner" style={{ marginRight: 8 }} />Generating draft…</>
          : "Generate Draft →"}
      </button>
    </form>
  );
}

// ── Step 2 ────────────────────────────────────────────────────────────────────
function Step2({ draft, companyForm, onJobStarted, onBack }) {
  function normDraft(v) {
    if (Array.isArray(v)) return v.map((s) => `• ${s}`).join("\n");
    return v ?? "";
  }

  const [fields, setFields] = useState({
    portfolio_name:          normDraft(draft.portfolio_name),
    fest_deliverables:       normDraft(draft.fest_deliverables),
    company_deliverables:    normDraft(draft.company_deliverables),
    brand_event_description: normDraft(draft.brand_event_description),
    question_answers:        "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function setF(k, v) { setFields((f) => ({ ...f, [k]: v })); }

  async function submit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await api.post(`/proposals/draft/${draft.session_id}/generate`, {
        portfolio_name:          fields.portfolio_name,
        fest_deliverables:       fields.fest_deliverables,
        company_deliverables:    fields.company_deliverables,
        brand_event_description: fields.brand_event_description,
        question_answers:        fields.question_answers,
      });
      // Backend now returns immediately with {job_id, proposal_id}
      onJobStarted(res.data.job_id, fields);
    } catch (err) {
      const d = err.response?.data?.detail;
      setError(typeof d === "string" ? d : Array.isArray(d) ? d.map(e => e.msg || JSON.stringify(e)).join("; ") : `Generation failed (${err.message})`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={submit}>
      {error && <div className="alert alert-error">{error}</div>}

      <div className="alert alert-info" style={{ marginBottom: 20 }}>
        Review and edit the AI-generated content below.{" "}
        <strong>What you type here will appear verbatim in the final PPT and cover letter.</strong>
      </div>

      {draft.questions?.length > 0 && (
        <div className="card">
          <div className="section-title">The AI has some questions</div>
          <div className="questions-box">
            <ul>{draft.questions.map((q, i) => <li key={i}>{q}</li>)}</ul>
          </div>
          <div className="form-group" style={{ marginTop: 10 }}>
            <label>Your answers</label>
            <textarea rows={4}
              placeholder="Answer all questions here. The AI will refine any fields you leave blank below."
              value={fields.question_answers}
              onChange={(e) => setF("question_answers", e.target.value)}
            />
          </div>
        </div>
      )}

      <div className="card">
        <div className="section-title">Portfolio Name</div>
        <div className="form-group">
          <input value={fields.portfolio_name} onChange={(e) => setF("portfolio_name", e.target.value)} required />
          <p className="form-note">✏ Your edits will appear verbatim in the PPT.</p>
        </div>
      </div>

      <div className="card">
        <div className="section-title">Deliverables from Festember</div>
        <div className="form-group">
          <textarea rows={8} value={fields.fest_deliverables} onChange={(e) => setF("fest_deliverables", e.target.value)} required />
          <p className="form-note">✏ Your edits will appear verbatim in the PPT.</p>
        </div>
      </div>

      <div className="card">
        <div className="section-title">Deliverables from {companyForm.company_name}</div>
        <div className="form-group">
          <textarea rows={6} value={fields.company_deliverables} onChange={(e) => setF("company_deliverables", e.target.value)} required />
          <p className="form-note">✏ Your edits will appear verbatim in the PPT. The AI will organise these into categories in the slides.</p>
        </div>
      </div>

      {companyForm.include_brand_engagement && (
        <div className="card">
          <div className="section-title">Brand Engagement Description</div>
          <div className="form-group">
            <textarea rows={3} value={fields.brand_event_description} onChange={(e) => setF("brand_event_description", e.target.value)} />
            <p className="form-note">✏ Your edits will appear verbatim in the PPT.</p>
          </div>
        </div>
      )}

      <div style={{ display: "flex", gap: 10 }}>
        <button type="button" className="btn btn-secondary" onClick={onBack} disabled={loading}>← Back</button>
        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading
            ? <><span className="spinner" style={{ marginRight: 8 }} />Starting…</>
            : "Generate PPT & Cover Letter →"}
        </button>
      </div>
    </form>
  );
}

// ── Draft polling step (between Step 1 submit and Step 2) ────────────────────
function StepDraftPolling({ draftJobId, originalForm, onDraft, onError }) {
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    let stopped = false;

    async function poll() {
      while (!stopped) {
        await new Promise((r) => setTimeout(r, 2500));
        if (stopped) break;
        try {
          const res = await api.get(`/proposals/draft-jobs/${draftJobId}`);
          const data = res.data;

          if (data.status === "done") {
            stopped = true;
            onDraft(data, originalForm);
            return;
          }

          if (data.status === "error") {
            stopped = true;
            setErrorMsg(data.error || "Draft generation failed. Please try again.");
            return;
          }
          // status === 'pending' — keep polling
        } catch (err) {
          if (err.response?.status === 404) {
            stopped = true;
            setErrorMsg("Server restarted during generation. Please try again.");
            return;
          }
          console.warn("Draft poll error:", err.message);
        }
      }
    }

    poll();
    return () => { stopped = true; };
  }, [draftJobId]);

  if (errorMsg) {
    return (
      <div>
        <div className="alert alert-error">
          <strong>Draft generation failed:</strong> {errorMsg}
        </div>
        <button className="btn btn-secondary" onClick={onError}>← Start Over</button>
      </div>
    );
  }

  return (
    <div className="card" style={{ textAlign: "center", padding: 48 }}>
      <div style={{ marginBottom: 20 }}>
        <span className="spinner" style={{ width: 32, height: 32, borderWidth: 3 }} />
      </div>
      <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>Generating draft…</div>
      <div style={{ fontSize: 13, color: "#71717a" }}>
        Analysing company details and drafting deliverables with AI…
      </div>
      <div style={{ fontSize: 12, color: "#a1a1aa", marginTop: 16 }}>
        This takes 20–60 seconds. You can switch tabs — we'll have it ready when you come back.
      </div>
    </div>
  );
}


// ── Polling step (between Step 2 and Step 3) ──────────────────────────────────
function StepPolling({ jobId, editedFields, onDone, onError }) {
  const [msgIndex, setMsgIndex] = useState(0);
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    // Cycle through status messages while waiting
    const msgTimer = setInterval(() => {
      setMsgIndex((i) => (i + 1) % PROGRESS_MESSAGES.length);
    }, 4000);
    return () => clearInterval(msgTimer);
  }, []);

  useEffect(() => {
    let stopped = false;

    async function poll() {
      while (!stopped) {
        await new Promise((r) => setTimeout(r, 3000));
        if (stopped) break;
        try {
          const res = await api.get(`/proposals/jobs/${jobId}`);
          const data = res.data;

          if (data.status === "done") {
            stopped = true;
            onDone({
              ...data,
              // Fall back to the user's own edited text if backend returns empty
              fest_deliverables:    data.fest_deliverables    || editedFields.fest_deliverables    || "",
              company_deliverables: data.company_deliverables || editedFields.company_deliverables || "",
            });
            return;
          }

          if (data.status === "error") {
            stopped = true;
            setErrorMsg(data.error_message || "Generation failed.");
            return;
          }
          // status === 'pending' — keep polling
        } catch (err) {
          // Network hiccup — keep trying
          console.warn("Poll error:", err.message);
        }
      }
    }

    poll();
    return () => { stopped = true; };
  }, [jobId]);

  if (errorMsg) {
    return (
      <div>
        <div className="alert alert-error">
          <strong>Generation failed:</strong> {errorMsg}
        </div>
        <p style={{ fontSize: 13, color: "#71717a", marginBottom: 16 }}>
          Your proposal quota has been used for this attempt. Contact admin if you need a reset.
        </p>
        <button className="btn btn-secondary" onClick={onError}>← Start Over</button>
      </div>
    );
  }

  return (
    <div className="card" style={{ textAlign: "center", padding: 48 }}>
      <div style={{ marginBottom: 20 }}>
        <span className="spinner" style={{ width: 32, height: 32, borderWidth: 3 }} />
      </div>
      <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 8 }}>Building your proposal…</div>
      <div style={{ fontSize: 13, color: "#71717a" }}>{PROGRESS_MESSAGES[msgIndex]}</div>
      <div style={{ fontSize: 12, color: "#a1a1aa", marginTop: 16 }}>
        This usually takes 30–60 seconds. Do not close this page.
      </div>
    </div>
  );
}

// ── Step 3 ────────────────────────────────────────────────────────────────────
function Step3({ result, onReset }) {
  const [copiedLetter, setCopiedLetter] = useState(false);
  const [copiedDeliv,  setCopiedDeliv]  = useState(false);
  const [pptWarning,     setPptWarning]     = useState(false);
  const [pptDownloading, setPptDownloading] = useState(false);

  function copyText(text, setCopied) {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function buildDeliverablesText() {
    const parts = [];
    if (result.fest_deliverables?.trim())
      parts.push("=== DELIVERABLES FROM FESTEMBER ===\n\n" + result.fest_deliverables.trim());
    if (result.company_deliverables?.trim())
      parts.push("=== DELIVERABLES FROM COMPANY ===\n\n" + result.company_deliverables.trim());
    return parts.join("\n\n");
  }

  function downloadText(content, filename) {
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  async function downloadPptx() {
    setPptDownloading(true);
    try {
      const res = await api.get("/proposals/download/pptx", {
        params: { folder: result.folder_name },
        responseType: "blob",
      });
      const cd = res.headers["content-disposition"] || "";
      const match = cd.match(/filename="?([^";]+)"?/);
      const filename = match?.[1] || `${result.folder_name}_proposal.pptx`;
      const url = URL.createObjectURL(res.data);
      const a   = document.createElement("a");
      a.href    = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setPptWarning(true);
    } catch (err) {
      alert("Download failed: " + (err.response?.data?.detail || err.message));
    } finally {
      setPptDownloading(false);
    }
  }

  const folder       = result.folder_name || "proposal";
  const festDeliv    = result.fest_deliverables?.trim()    || "";
  const companyDeliv = result.company_deliverables?.trim() || "";
  const hasDeliverables = festDeliv || companyDeliv;

  return (
    <div>
      <div className="alert alert-success">Proposal generated successfully!</div>

      {/* ── Download buttons ── */}
      <div className="card">
        <div className="section-title">Download Files</div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <button className="btn btn-primary" onClick={downloadPptx} disabled={pptDownloading}>
            {pptDownloading ? "Downloading…" : "Download PPT"}
          </button>
          <button className="btn btn-secondary"
            onClick={() => downloadText(result.cover_letter || "", `${folder}_cover_letter.txt`)}>
            Download Cover Letter (.txt)
          </button>
          <button className="btn btn-secondary"
            onClick={() => downloadText(buildDeliverablesText(), `${folder}_deliverables.txt`)}
            disabled={!hasDeliverables}>
            Download Deliverables (.txt)
          </button>
        </div>

        {pptWarning && (
          <div className="alert alert-warning" style={{ marginTop: 12, marginBottom: 0 }}>
            <strong>Important — please verify before sending:</strong>
            <ul style={{ margin: "6px 0 0 0", paddingLeft: 20, lineHeight: 1.7 }}>
              <li>Check every slide for AI-generated inaccuracies or placeholder text that wasn't filled in.</li>
              <li>
                In particular, verify the <strong>"Deliverables from Company"</strong> slide — it is
                auto-filled by AI and may be incomplete or incorrectly categorised.
              </li>
              <li>Review banner / standee counts and digital post numbers on each cluster slide.</li>
            </ul>
          </div>
        )}
      </div>

      {/* ── Cover Letter ── */}
      {result.cover_letter && (
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
            <div className="section-title" style={{ marginBottom: 0 }}>Cover Letter</div>
            <button className="btn btn-secondary btn-sm"
              onClick={() => copyText(result.cover_letter || "", setCopiedLetter)}>
              {copiedLetter ? "Copied!" : "Copy"}
            </button>
          </div>
          <pre style={{ whiteSpace: "pre-wrap", fontSize: 13, lineHeight: 1.6, fontFamily: "inherit" }}>
            {result.cover_letter}
          </pre>
        </div>
      )}

      {/* ── Deliverables ── */}
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
          <div className="section-title" style={{ marginBottom: 0 }}>Deliverables</div>
          {hasDeliverables && (
            <button className="btn btn-secondary btn-sm"
              onClick={() => copyText(buildDeliverablesText(), setCopiedDeliv)}>
              {copiedDeliv ? "Copied!" : "Copy All"}
            </button>
          )}
        </div>

        {festDeliv ? (
          <>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>From Festember</div>
            <pre style={{ whiteSpace: "pre-wrap", fontSize: 13, lineHeight: 1.6, fontFamily: "inherit", marginBottom: 16 }}>
              {festDeliv}
            </pre>
          </>
        ) : (
          <p className="form-hint" style={{ marginBottom: 16 }}>Festember deliverables not available.</p>
        )}

        {companyDeliv ? (
          <>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>From Company</div>
            <pre style={{ whiteSpace: "pre-wrap", fontSize: 13, lineHeight: 1.6, fontFamily: "inherit" }}>
              {companyDeliv}
            </pre>
          </>
        ) : (
          <p className="form-hint">Company deliverables not available.</p>
        )}
      </div>

      <button className="btn btn-primary" onClick={onReset}>Generate Another →</button>
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function Generate() {
  const [step,          setStep]         = useState(1);
  const [draftJobId,    setDraftJobId]   = useState(null);
  const [draft,         setDraft]        = useState(null);
  const [companyForm,   setCompanyForm]  = useState(null);
  const [jobId,         setJobId]        = useState(null);
  const [editedFields,  setEditedFields] = useState(null);
  const [result,        setResult]       = useState(null);
  const [usage,         setUsage]        = useState(null);

  useEffect(() => {
    api.get("/proposals/usage").then((r) => setUsage(r.data)).catch(() => {});
  }, [step]);

  // Step 1 submits → backend returns draft_job_id immediately
  function handleDraftJobStarted(djid, form) {
    setDraftJobId(djid);
    setCompanyForm(form);
    setStep("draft-polling");
  }

  // Draft polling completes → backend draft data arrives → show Step 2
  function handleDraft(d, f) {
    setDraft(d);
    setCompanyForm(f);
    setStep(2);
  }

  // Step 2 submits → PPT pipeline job starts
  function handleJobStarted(jid, fields) {
    setJobId(jid);
    setEditedFields(fields);
    setStep("polling");
  }

  function handleDone(r) { setResult(r); setStep(3); }

  function reset() {
    setStep(1);
    setDraftJobId(null);
    setDraft(null);
    setCompanyForm(null);
    setJobId(null);
    setEditedFields(null);
    setResult(null);
  }

  return (
    <div>
      <div className="page-title">Generate Proposal</div>
      <UsageBar usage={usage} />
      {step === 1               && <Step1 onDraftJobStarted={handleDraftJobStarted} />}
      {step === "draft-polling" && (
        <StepDraftPolling
          draftJobId={draftJobId}
          originalForm={companyForm}
          onDraft={handleDraft}
          onError={reset}
        />
      )}
      {step === 2               && <Step2 draft={draft} companyForm={companyForm} onJobStarted={handleJobStarted} onBack={() => setStep(1)} />}
      {step === "polling"       && <StepPolling jobId={jobId} editedFields={editedFields} onDone={handleDone} onError={reset} />}
      {step === 3               && <Step3 result={result} onReset={reset} />}
    </div>
  );
}
