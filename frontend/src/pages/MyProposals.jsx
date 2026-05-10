import { useState, useEffect } from "react";
import api from "../api/client";

export default function MyProposals() {
  const [proposals, setProposals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedError, setExpandedError] = useState(null);

  useEffect(() => {
    api.get("/proposals/my")
      .then((r) => setProposals(r.data))
      .finally(() => setLoading(false));
  }, []);

  // Use folder_name directly; fall back to parsing output_folder for old records
  function getFolder(p) {
    if (p.folder_name) return p.folder_name;
    return p.output_folder ? p.output_folder.replace(/\\/g, "/").split("/").pop() : null;
  }

  async function downloadFile(type, folder) {
    if (!folder) return;
    try {
      const res = await api.get(`/proposals/download/${type}`, {
        params: { folder },
        responseType: "blob",
      });
      const cd = res.headers["content-disposition"] || "";
      const match = cd.match(/filename="?([^";]+)"?/);
      const filename = match?.[1] || `${folder}_${type === "pptx" ? "proposal.pptx" : "cover_letter.txt"}`;
      const blobUrl = URL.createObjectURL(res.data);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(blobUrl);
    } catch (err) {
      alert("Download failed: " + (err.response?.data?.detail || err.message));
    }
  }

  if (loading) return <div>Loading…</div>;

  return (
    <div>
      <div className="page-title">My Proposals</div>
      {proposals.length === 0 ? (
        <div className="card">No proposals generated yet.</div>
      ) : (
        <div className="card">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Company</th>
                <th>Tier</th>
                <th>Clusters</th>
                <th>Status</th>
                <th>Date</th>
                <th>Downloads</th>
              </tr>
            </thead>
            <tbody>
              {proposals.map((p, i) => {
                const clusters = (() => { try { return JSON.parse(p.clusters).join(", "); } catch { return p.clusters; } })();
                const folder = getFolder(p);
                return (
                  <>
                    <tr key={p.id}>
                      <td>{i + 1}</td>
                      <td><strong>{p.company_name}</strong></td>
                      <td>Tier {p.tier}</td>
                      <td style={{ maxWidth: 180 }}>{clusters}</td>
                      <td>
                        {p.status === "error" ? (
                          <button
                            className="tag tag-error"
                            style={{ background: "none", border: "none", cursor: "pointer", textDecoration: "underline dotted" }}
                            onClick={() => setExpandedError(expandedError === p.id ? null : p.id)}
                            title="Click to see error details"
                          >error</button>
                        ) : (
                          <span className={`tag tag-${p.status === "done" ? "done" : "pending"}`}>
                            {p.status}
                          </span>
                        )}
                      </td>
                      <td style={{ whiteSpace: "nowrap" }}>{p.created_at?.slice(0, 16).replace("T", " ")}</td>
                      <td>
                        {p.status === "done" && folder && (
                          <div style={{ display: "flex", gap: 6 }}>
                            <button className="btn btn-secondary btn-sm" onClick={() => downloadFile("pptx", folder)}>PPT</button>
                            <button className="btn btn-secondary btn-sm" onClick={() => downloadFile("letter", folder)}>Letter</button>
                          </div>
                        )}
                      </td>
                    </tr>
                    {expandedError === p.id && p.error_message && (
                      <tr key={`err-${p.id}`}>
                        <td colSpan={7}>
                          <div className="alert alert-error" style={{ margin: "2px 0", fontSize: 12, whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
                            {p.error_message}
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
