"""
Proposal generation — two-phase flow:

  POST /proposals/draft
    Takes company details + optional extra context.
    Calls LLM to produce deliverables and any clarifying questions.
    Manager info is pulled from the user's profile automatically.

  POST /proposals/draft/{session_id}/generate
    Takes the (user-edited) deliverables + answers to LLM questions.
    Creates a proposal record immediately (status=pending) and starts a
    background task so the 30–60 s pipeline doesn't block the HTTP response.
    Returns {job_id, proposal_id} immediately.

  GET /proposals/jobs/{job_id}
    Poll for background-task status.
    Returns {status, ...result} where status is pending | done | error.

  GET /proposals/download/pptx?folder={folder_name}
    Download the generated PPTX for a proposal output folder.

  GET /proposals/download/letter?folder={folder_name}
    Download the cover letter text file.

  POST /proposals/upload-logo
    Upload a company logo image; returns the server-side path.
"""
import json
import logging
import shutil
import uuid
from pathlib import Path
from typing import List, Optional, Union

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator

from backend.auth import get_current_user
from backend.config import OUTPUTS_DIR, RESOURCES_DIR, TIER_POSTS
from backend.database import get_db
from backend.services.llm import generate_cover_letter, generate_draft, reformat_deliverables
from backend.services.pptx_editor import run_pipeline
from backend.services.rate_limiter import check_and_increment, get_usage

log = logging.getLogger(__name__)

router = APIRouter(prefix="/proposals", tags=["proposals"])

_LOGOS_DIR = RESOURCES_DIR / "logos"
_LOGOS_DIR.mkdir(parents=True, exist_ok=True)


# ── Schemas ───────────────────────────────────────────────────────────────────

class DraftRequest(BaseModel):
    company_name: str
    tier: int
    clusters: list
    banner_count: int
    logo_path: Optional[str] = ""
    outreach_event: Optional[str] = "Gigahertz"
    outreach_city: Optional[str] = "Bangalore"
    include_csr: Optional[bool] = False
    include_pronite: Optional[bool] = True
    include_event_association: Optional[bool] = True
    include_cluster: Optional[bool] = True
    include_brand_engagement: Optional[bool] = True
    include_outreach: Optional[bool] = True
    extra_context: Optional[str] = ""


class GenerateRequest(BaseModel):
    portfolio_name: Optional[str] = None
    fest_deliverables: Optional[Union[str, List[str]]] = None
    company_deliverables: Optional[Union[str, List[str]]] = None
    brand_event_description: Optional[str] = None
    question_answers: Optional[str] = None

    @field_validator("fest_deliverables", "company_deliverables", mode="before")
    @classmethod
    def coerce_list_to_str(cls, v):
        if isinstance(v, list):
            return "\n".join(f"• {item}" for item in v if item)
        return v


def _get_profile(user_id: int) -> dict:
    with get_db() as conn:
        row = conn.execute(
            "SELECT full_name, designation, phone, email FROM user_profiles WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if row:
        return dict(row)
    return {"full_name": "", "designation": "", "phone": "", "email": ""}


# ── Logo upload ───────────────────────────────────────────────────────────────

@router.post("/upload-logo")
async def upload_logo(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    allowed = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed:
        raise HTTPException(400, f"Logo must be an image file ({', '.join(allowed)})")

    unique_name = f"{uuid.uuid4().hex}{suffix}"
    dest = _LOGOS_DIR / unique_name
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    return {"logo_path": str(dest)}


# ── Phase 1: Draft ────────────────────────────────────────────────────────────

@router.post("/draft")
def create_draft(req: DraftRequest, current_user: dict = Depends(get_current_user)):
    if req.tier not in (1, 2, 3):
        raise HTTPException(400, "tier must be 1, 2, or 3")
    if not req.clusters:
        raise HTTPException(400, "at least one cluster is required")

    profile = _get_profile(current_user["id"])
    missing = [f for f in ("full_name", "designation", "email") if not profile.get(f, "").strip()]
    if missing:
        raise HTTPException(400, f"Complete your profile before generating. Missing: {', '.join(missing)}.")

    posts_count = TIER_POSTS[req.tier]

    try:
        draft = generate_draft(
            company_name=req.company_name,
            tier=req.tier,
            clusters=req.clusters,
            banner_count=req.banner_count,
            posts_count=posts_count,
            extra_context=req.extra_context or "",
        )
    except Exception as exc:
        raise HTTPException(500, f"LLM draft failed: {exc}") from exc

    log.info("draft keys/types: %s", {k: type(v).__name__ for k, v in draft.items()})
    questions = draft.get("questions", [])
    if not isinstance(questions, list):
        questions = []
    questions = [str(q) for q in questions]

    session_id = uuid.uuid4().hex

    with get_db() as conn:
        conn.execute(
            """INSERT INTO draft_sessions (
                id, user_id, company_name, tier, clusters, banner_count,
                logo_path, manager_name, manager_designation, manager_phone,
                manager_email, outreach_city, include_csr, extra_context,
                llm_questions, fest_deliverables, company_deliverables,
                brand_event_description, portfolio_name
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                session_id,
                current_user["id"],
                req.company_name,
                req.tier,
                json.dumps(req.clusters),
                req.banner_count,
                req.logo_path or "",
                "",
                "",
                "",
                "",
                req.outreach_city or "Bangalore",
                1 if req.include_csr else 0,
                json.dumps({
                    "extra_context":             req.extra_context or "",
                    "outreach_event":            req.outreach_event or "Gigahertz",
                    "include_pronite":           req.include_pronite,
                    "include_event_association": req.include_event_association,
                    "include_cluster":           req.include_cluster,
                    "include_brand_engagement":  req.include_brand_engagement,
                    "include_outreach":          req.include_outreach,
                }),
                json.dumps(questions),
                str(draft.get("fest_deliverables", "")),
                str(draft.get("company_deliverables", "")),
                str(draft.get("brand_event_description", "")),
                str(draft.get("portfolio_name", "")),
            ),
        )

    return {
        "session_id":               session_id,
        "portfolio_name":           str(draft.get("portfolio_name", "")),
        "fest_deliverables":        str(draft.get("fest_deliverables", "")),
        "company_deliverables":     str(draft.get("company_deliverables", "")),
        "brand_event_description":  str(draft.get("brand_event_description", "")),
        "questions":                questions,
    }


# ── Phase 2: Kick off background generation ───────────────────────────────────

@router.post("/draft/{session_id}/generate")
def generate_from_draft(
    session_id: str,
    req: GenerateRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM draft_sessions WHERE id = ? AND user_id = ?",
            (session_id, current_user["id"]),
        ).fetchone()

    if not row:
        raise HTTPException(404, "Draft session not found or does not belong to you")

    # Enforce rate limit before starting the job (counts even if generation fails)
    check_and_increment(current_user["id"])

    profile = _get_profile(current_user["id"])

    # Create a pending proposal record and get its id for polling
    job_id = uuid.uuid4().hex
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO proposals
               (user_id, company_name, tier, clusters, output_folder, status, job_id)
               VALUES (?,?,?,?,?,'pending',?)""",
            (
                current_user["id"],
                row["company_name"],
                row["tier"],
                row["clusters"],
                "",
                job_id,
            ),
        )
        proposal_id = cursor.lastrowid

    # Fire off the pipeline in the background
    background_tasks.add_task(
        _run_pipeline_bg,
        proposal_id=proposal_id,
        job_id=job_id,
        session_id=session_id,
        row=dict(row),
        req_dict={
            "portfolio_name":          req.portfolio_name,
            "fest_deliverables":       req.fest_deliverables,
            "company_deliverables":    req.company_deliverables,
            "brand_event_description": req.brand_event_description,
            "question_answers":        req.question_answers,
        },
        username=current_user["username"],
        profile=profile,
    )

    return {"job_id": job_id, "proposal_id": proposal_id}


def _run_pipeline_bg(
    proposal_id: int,
    job_id: str,
    session_id: str,
    row: dict,
    req_dict: dict,
    username: str,
    profile: dict,
):
    """Background worker: runs LLM + PPT pipeline and updates the proposal record."""
    try:
        # ── Parse session context ──────────────────────────────────────────────
        try:
            ctx = json.loads(row["extra_context"])
            extra_context_text  = ctx.get("extra_context", "")
            outreach_event      = ctx.get("outreach_event", "Gigahertz")
            include_pronite     = ctx.get("include_pronite", True)
            include_event_assoc = ctx.get("include_event_association", True)
            include_cluster     = ctx.get("include_cluster", True)
            include_brand       = ctx.get("include_brand_engagement", True)
            include_outreach    = ctx.get("include_outreach", True)
        except (json.JSONDecodeError, TypeError):
            extra_context_text  = row.get("extra_context") or ""
            outreach_event = "Gigahertz"
            include_pronite = include_event_assoc = include_cluster = include_brand = include_outreach = True

        clusters = json.loads(row["clusters"])

        fest_deliverables       = req_dict.get("fest_deliverables") or ""
        company_deliverables    = req_dict.get("company_deliverables") or ""
        brand_event_description = req_dict.get("brand_event_description") or ""
        portfolio_name          = req_dict.get("portfolio_name") or ""
        question_answers        = req_dict.get("question_answers") or ""

        # ── Optional LLM re-run with user's question answers ──────────────────
        if question_answers.strip():
            posts_count = TIER_POSTS[row["tier"]]
            extra = extra_context_text + "\n\nAnswers to clarifying questions:\n" + question_answers
            updated = generate_draft(
                company_name=row["company_name"],
                tier=row["tier"],
                clusters=clusters,
                banner_count=row["banner_count"],
                posts_count=posts_count,
                extra_context=extra,
            )
            if not fest_deliverables.strip():
                fest_deliverables = updated.get("fest_deliverables", "")
            if not company_deliverables.strip():
                company_deliverables = updated.get("company_deliverables", "")
            if not brand_event_description.strip():
                brand_event_description = updated.get("brand_event_description", "")
            if not portfolio_name.strip():
                portfolio_name = updated.get("portfolio_name", "")

        # ── Reformat deliverables ─────────────────────────────────────────────
        fest_deliverables    = reformat_deliverables(fest_deliverables,    "Deliverables from Festember")
        company_deliverables = reformat_deliverables(company_deliverables, f"Deliverables from {row['company_name']}")

        # ── Run PPT pipeline ──────────────────────────────────────────────────
        ppt_result = run_pipeline(
            username=username,
            company_name=row["company_name"],
            tier=row["tier"],
            clusters=clusters,
            banner_count=row["banner_count"],
            logo_path=row.get("logo_path") or "",
            manager_name=profile["full_name"],
            manager_designation=profile["designation"],
            manager_phone=profile["phone"],
            manager_email=profile["email"],
            portfolio_name=portfolio_name,
            fest_deliverables=fest_deliverables,
            company_deliverables=company_deliverables,
            brand_event_description=brand_event_description,
            outreach_event=outreach_event,
            outreach_city=row.get("outreach_city") or "Bangalore",
            include_csr=bool(row.get("include_csr")),
            include_pronite=include_pronite,
            include_event_association=include_event_assoc,
            include_cluster=include_cluster,
            include_brand_engagement=include_brand,
            include_outreach=include_outreach,
        )

        # ── Generate cover letter ─────────────────────────────────────────────
        try:
            cover_letter = generate_cover_letter(
                company_name=row["company_name"],
                tier=row["tier"],
                portfolio_name=portfolio_name,
                fest_deliverables=fest_deliverables,
                company_deliverables=company_deliverables,
                manager_name=profile["full_name"],
                manager_designation=profile["designation"],
                manager_phone=profile.get("phone", ""),
                manager_email=profile.get("email", ""),
            )
        except Exception:
            log.exception("Cover letter generation failed; continuing without it")
            cover_letter = ""

        # ── Write text files to output folder ─────────────────────────────────
        out_folder = ppt_result["output_folder"]
        try:
            with open(out_folder + "/cover_letter.txt", "w", encoding="utf-8") as f:
                f.write(cover_letter)
        except Exception:
            log.exception("Failed to write cover_letter.txt")

        try:
            deliv_text = (
                f"=== DELIVERABLES FROM FESTEMBER ===\n\n{fest_deliverables}\n\n"
                f"=== DELIVERABLES FROM {row['company_name'].upper()} ===\n\n{company_deliverables}"
            )
            with open(out_folder + "/deliverables.txt", "w", encoding="utf-8") as f:
                f.write(deliv_text)
        except Exception:
            log.exception("Failed to write deliverables.txt")

        # ── Update proposal record → done ─────────────────────────────────────
        folder_name = ppt_result["folder_name"]
        with get_db() as conn:
            conn.execute(
                """UPDATE proposals SET
                     status='done', output_folder=?, folder_name=?,
                     cover_letter=?, fest_deliverables=?, company_deliverables=?
                   WHERE id=?""",
                (
                    out_folder, folder_name,
                    cover_letter, fest_deliverables, company_deliverables,
                    proposal_id,
                ),
            )
            conn.execute("DELETE FROM draft_sessions WHERE id = ?", (session_id,))

        log.info("Pipeline completed: proposal_id=%s  folder=%s", proposal_id, folder_name)

    except Exception as exc:
        log.exception("Pipeline failed for proposal_id=%s", proposal_id)
        error_msg = str(exc)[:2000]
        with get_db() as conn:
            conn.execute(
                "UPDATE proposals SET status='error', error_message=? WHERE id=?",
                (error_msg, proposal_id),
            )


# ── Job status polling ────────────────────────────────────────────────────────

@router.get("/jobs/{job_id}")
def get_job_status(job_id: str, current_user: dict = Depends(get_current_user)):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM proposals WHERE job_id = ? AND user_id = ?",
            (job_id, current_user["id"]),
        ).fetchone()

    if not row:
        raise HTTPException(404, "Job not found")

    status = row["status"]
    result: dict = {"status": status}

    if status == "done":
        result.update({
            "folder_name":         row["folder_name"] or "",
            "cover_letter":        row["cover_letter"] or "",
            "fest_deliverables":   row["fest_deliverables"] or "",
            "company_deliverables": row["company_deliverables"] or "",
        })
    elif status == "error":
        result["error_message"] = row["error_message"] or "An unknown error occurred."

    return result


# ── Download endpoints ────────────────────────────────────────────────────────

@router.get("/download/pptx")
def download_pptx(folder: str, current_user: dict = Depends(get_current_user)):
    out_dir = OUTPUTS_DIR / current_user["username"] / folder
    pptx_file = out_dir / "proposal.pptx"
    if not pptx_file.exists():
        raise HTTPException(404, "PPTX file not found")
    return FileResponse(
        path=str(pptx_file),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=f"{folder}_proposal.pptx",
    )


@router.get("/download/letter")
def download_letter(folder: str, current_user: dict = Depends(get_current_user)):
    out_dir = OUTPUTS_DIR / current_user["username"] / folder
    letter_file = out_dir / "cover_letter.txt"
    if not letter_file.exists():
        raise HTTPException(404, "Cover letter not found")
    return FileResponse(
        path=str(letter_file),
        media_type="text/plain",
        filename=f"{folder}_cover_letter.txt",
    )


@router.get("/download/deliverables")
def download_deliverables(folder: str, current_user: dict = Depends(get_current_user)):
    out_dir = OUTPUTS_DIR / current_user["username"] / folder
    deliv_file = out_dir / "deliverables.txt"
    if not deliv_file.exists():
        raise HTTPException(404, "Deliverables file not found")
    return FileResponse(
        path=str(deliv_file),
        media_type="text/plain",
        filename=f"{folder}_deliverables.txt",
    )


# ── Utility ───────────────────────────────────────────────────────────────────

@router.get("/usage")
def usage(current_user: dict = Depends(get_current_user)):
    return get_usage(current_user["id"])


@router.get("/my")
def my_proposals(current_user: dict = Depends(get_current_user)):
    with get_db() as conn:
        rows = conn.execute(
            """SELECT id, company_name, tier, clusters, output_folder, folder_name,
                      status, error_message, created_at
               FROM proposals WHERE user_id = ? ORDER BY created_at DESC""",
            (current_user["id"],),
        ).fetchall()
    return [dict(r) for r in rows]
