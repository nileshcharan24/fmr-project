"""
Full PPT generation pipeline.

Strategy:
- python-pptx for structural changes (delete, duplicate slides) + save
- Direct ZIP byte editing for text replacement — searches by content, not by
  slide index, because python-pptx reorders slide rels on save
- python-pptx for logo insertion (needs package system for image embedding)

Slide positions (1-based after python-pptx load+save = filename order):
   5 = Association/logo slide
  10 = Pronite Partnership      — tier 1 only
  11 = Event Association        — tier 1 & 2 always deleted; tier 3 optional
  12 = Cluster slide            — duplicated per cluster
  13 = Brand Engagement         — tier 1 only
  14 = Outreach                 — tier 1 only
  15 = CSR                      — tier 1 always; tier 2 optional
  17 = Deliverables-Header      — section header for company deliverables
  18 = Deliverables-A           — first structured deliverables slide (filled)
  19 = Deliverables-B           — duplicate (always deleted after filling A)
"""
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.config import (
    LOGO_LEFT_INCHES,
    LOGO_TOP_INCHES,
    LOGO_WIDTH_INCHES,
    OUTPUTS_DIR,
    TEMP_DIR,
    TEMPLATE_PPTX,
    TIER_POSTS,
)
from backend.scripts.office.pptx_ops import (
    cleanup_orphaned_slides,
    delete_slides_by_1based_indices,
    delete_slide_at_position,
    duplicate_slide_zip,
    fill_company_deliverables_slide,
    find_slides_by_content,
    insert_logo,
    load,
    replace_in_pptx_file,
    replace_in_slides_matching,
    save,
)
from backend.services.llm import generate_csr_event, structure_company_deliverables
from backend.services.resource_reader import read_cluster_descriptions


_PRONITE_SLIDE     = 10
_EVENT_ASSOC_SLIDE = 11
_CLUSTER_SLIDE     = 12
_BRAND_SLIDE       = 13
_OUTREACH_SLIDE    = 14
_CSR_SLIDE         = 15
_LOGO_SLIDE        = 5

# Cap for total banners + standees the company gets (combined across all slides)
_TOTAL_BANNER_CAP = 6
_BRAND_BANNERS    = 1     # Brand engagement always gets exactly 1


def run_pipeline(
    username: str,
    company_name: str,
    tier: int,
    clusters: list,
    banner_count: int,
    logo_path: str,
    manager_name: str,
    manager_designation: str,
    manager_phone: str,
    manager_email: str,
    portfolio_name: str,
    fest_deliverables: str,
    company_deliverables: str,
    brand_event_description: str,
    outreach_event: str = "Gigahertz",
    outreach_city: str = "Bangalore",
    include_csr: bool = False,
    include_pronite: bool = True,
    include_event_association: bool = True,
    include_cluster: bool = True,
    include_brand_engagement: bool = True,
    include_outreach: bool = True,
) -> dict:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex[:8]
    temp_pptx = TEMP_DIR / f"working_{run_id}.pptx"
    shutil.copy2(str(TEMPLATE_PPTX), str(temp_pptx))

    try:
        # ── STEP 1: Delete tier-specific + user-excluded slides ───────────────
        slides_to_delete = _get_slides_to_delete(
            tier, include_csr,
            include_pronite=include_pronite,
            include_event_association=include_event_association,
            include_cluster=include_cluster,
            include_brand_engagement=include_brand_engagement,
            include_outreach=include_outreach,
        )
        prs = load(str(temp_pptx))
        delete_slides_by_1based_indices(prs, slides_to_delete)
        save(prs, str(temp_pptx))
        # Remove orphan slide files left by python-pptx's deletion
        cleanup_orphaned_slides(str(temp_pptx))

        # ── STEP 2: Duplicate cluster slide at ZIP level ──────────────────────
        # python-pptx's duplicate corrupts image rId mapping, so we do this
        # by literally copying the source slide XML + rels in the package.
        cluster_1based = _adjusted_index(_CLUSTER_SLIDE, slides_to_delete)
        will_have_clusters = include_cluster
        extra_copies = (len(clusters) - 1) if (will_have_clusters and clusters) else 0

        if cluster_1based and extra_copies > 0:
            duplicate_slide_zip(str(temp_pptx), cluster_1based, extra_copies)

        # ── STEP 3: Compute banner counts ─────────────────────────────────────
        # Total ≤ 6 across the whole proposal
        # Brand engagement: always 1 (if included)
        # Cluster: ≤2 per cluster, total cluster banners + brand ≤ 6
        n_clusters = len(clusters) if will_have_clusters else 0
        brand_in_play = include_brand_engagement
        brand_banners = _BRAND_BANNERS if brand_in_play else 0
        cluster_budget = _TOTAL_BANNER_CAP - brand_banners
        if n_clusters > 0:
            per_cluster_banners = max(1, min(banner_count, 2, cluster_budget // n_clusters))
        else:
            per_cluster_banners = banner_count

        # Event association banners (tier 3 with event assoc): cap at remaining budget
        event_assoc_banners = max(1, min(banner_count, _TOTAL_BANNER_CAP))

        # ── STEP 4: Global replacements (NO <number> here — done per-slide) ──
        posts_count = TIER_POSTS[tier]
        global_replacements = {
            "Company Name":  company_name,
            "company name":  company_name,
            "Company name":  company_name,
            "COMPANY NAME":  company_name,
            "company":       company_name,
            "Company":       company_name,
            "COMPANY":       company_name,
            "Portfolio":     portfolio_name,
            "portfolio":     portfolio_name,
            "#posts":        posts_count,
            "Name":          manager_name,
            "Designation":   manager_designation,
            "Phone No":      manager_phone,
            "Email":         manager_email,
            "event name":    clusters[0] if clusters else "Festember",
        }
        replace_in_pptx_file(str(temp_pptx), global_replacements)

        # ── STEP 5: Cluster slides — fill per-cluster ─────────────────────────
        if will_have_clusters:
            cluster_descriptions = read_cluster_descriptions()
            cluster_entity_anchor = "&lt;cluster name&gt;"

            for cluster_name in clusters:
                description = cluster_descriptions.get(cluster_name, "")
                cluster_replacements = {
                    "cluster name": cluster_name,
                    "cluster":      cluster_name,
                    "Brief explanation about the cluster and the various events involved": description,
                    "number":       str(per_cluster_banners),
                }
                replace_in_slides_matching(
                    str(temp_pptx),
                    match_text=cluster_entity_anchor,
                    replacements=cluster_replacements,
                    max_slides=1,
                )

        # ── STEP 6: Brand engagement slide — banners=1, description ──────────
        if include_brand_engagement:
            brand_replacements = {"number": str(brand_banners)}
            if brand_event_description.strip():
                brand_replacements["Brief explanation of event"] = brand_event_description
            replace_in_slides_matching(
                str(temp_pptx),
                match_text="&lt;Brief explanation of event&gt;",
                replacements=brand_replacements,
            )

        # ── STEP 7: Event association slide ──────────────────────────────────
        if include_event_association:
            replace_in_slides_matching(
                str(temp_pptx),
                match_text="Event Association",
                replacements={"number": str(event_assoc_banners)},
                max_slides=1,
            )

        # ── STEP 8: Outreach slide ────────────────────────────────────────────
        if include_outreach:
            outreach_desc = _build_outreach_desc(outreach_event, outreach_city)
            replace_in_slides_matching(
                str(temp_pptx),
                match_text="&lt;city&gt;",
                replacements={
                    "city":       outreach_city,
                    "event name": outreach_event,
                    "Brief description of the outreach event": outreach_desc,
                },
            )

        # ── STEP 9: CSR slide — auto-fill event description ──────────────────
        csr_active = include_csr
        if csr_active:
            csr_event = generate_csr_event(company_name, portfolio_name)
            replace_in_slides_matching(
                str(temp_pptx),
                match_text="&lt;event description, if applicable&gt;",
                replacements={"event description, if applicable": csr_event},
            )

        # ── STEP 10: Company deliverables structured slides ──────────────────
        import logging as _logging
        _log = _logging.getLogger(__name__)

        deliverables_positions = find_slides_by_content(
            str(temp_pptx), "SOCIAL MEDIA MARKETING"
        )
        _log.info("DELIV step10: positions=%s  company_deliverables_len=%d",
                  deliverables_positions, len(company_deliverables.strip()))

        # Delete the DUPLICATE first — so python-pptx never sees the filled XML,
        # which avoids lxml choking on any XML we wrote at the zip level.
        if len(deliverables_positions) > 1:
            delete_slide_at_position(str(temp_pptx), deliverables_positions[1])
            cleanup_orphaned_slides(str(temp_pptx))
            # Re-find positions now that duplicate is gone
            deliverables_positions = find_slides_by_content(
                str(temp_pptx), "SOCIAL MEDIA MARKETING"
            )
            _log.info("DELIV step10 after dup-delete: positions=%s", deliverables_positions)

        if deliverables_positions and company_deliverables.strip():
            sections = structure_company_deliverables(company_deliverables, company_name)
            _log.info("DELIV step10: sections count=%d  section_headings=%s",
                      len(sections), [s[0] for s in sections])
            if sections:
                fill_company_deliverables_slide(
                    str(temp_pptx), deliverables_positions[0], sections
                )
                _log.info("DELIV step10: fill_company_deliverables_slide DONE")
        else:
            _log.warning("DELIV step10: SKIPPED — positions=%s  has_content=%s",
                         deliverables_positions, bool(company_deliverables.strip()))

        # ── STEP 11: Move to output folder ────────────────────────────────────
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_company = re.sub(r'[^\w\-]', '_', company_name)
        folder_name = f"{safe_company}_{timestamp}"
        out_dir = OUTPUTS_DIR / username / folder_name
        out_dir.mkdir(parents=True, exist_ok=True)
        out_pptx = out_dir / "proposal.pptx"
        shutil.copy2(str(temp_pptx), str(out_pptx))

        # ── STEP 12: Insert logo on Association slide ─────────────────────────
        if logo_path and Path(logo_path).exists():
            # Logo slide is at position 5; deletions before pos 5 are zero,
            # cluster duplications happen after pos 5 → no shift.
            logo_slide_1based = _LOGO_SLIDE
            try:
                prs_final = load(str(out_pptx))
                insert_logo(
                    prs_final, logo_slide_1based, logo_path,
                    LOGO_LEFT_INCHES, LOGO_TOP_INCHES, LOGO_WIDTH_INCHES,
                )
                save(prs_final, str(out_pptx))
            except Exception as exc:
                # Logo insertion failure shouldn't break the whole proposal
                import logging
                logging.getLogger(__name__).warning("Logo insertion failed: %s", exc)

        return {
            "pptx_path":     str(out_pptx),
            "output_folder": str(out_dir),
            "folder_name":   folder_name,
        }

    finally:
        if temp_pptx.exists():
            temp_pptx.unlink()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_slides_to_delete(
    tier: int,
    include_csr: bool,
    include_pronite: bool = True,
    include_event_association: bool = True,
    include_cluster: bool = True,
    include_brand_engagement: bool = True,
    include_outreach: bool = True,
) -> list:
    slides = []

    if not include_pronite:
        slides.append(_PRONITE_SLIDE)
    if not include_brand_engagement:
        slides.append(_BRAND_SLIDE)
    if not include_outreach:
        slides.append(_OUTREACH_SLIDE)
    if not include_csr:
        slides.append(_CSR_SLIDE)
    if not include_event_association:
        slides.append(_EVENT_ASSOC_SLIDE)
    if not include_cluster:
        slides.append(_CLUSTER_SLIDE)

    return list(dict.fromkeys(slides))  # dedupe, preserve order


def _adjusted_index(original_1based: int, deleted_1based: list) -> Optional[int]:
    if original_1based in deleted_1based:
        return None
    shift = sum(1 for d in deleted_1based if d < original_1based)
    return original_1based - shift


def _build_outreach_desc(outreach_event: str, outreach_city: str) -> str:
    """
    Use cluster_descriptions.json for known events (user-editable).
    Falls back to hardcoded descriptions for others.
    """
    cluster_data = read_cluster_descriptions()

    json_key_map = {
        "Gigahertz":                    "Gigahertz",
        "Festember Football League":    "FFL",
        "Rolling Reels Film Festival":  "Rolling Reels",
    }
    json_key = json_key_map.get(outreach_event)
    if json_key and json_key in cluster_data:
        base = cluster_data[json_key]
        return f"{base} This edition will be held in {outreach_city}."

    return f"{outreach_event} held in {outreach_city}."
