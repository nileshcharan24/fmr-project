import json
import os
import re

import google.generativeai as genai
import google.generativeai.client as _gc

from backend.config import GEMINI_MODEL
from backend.services.resource_reader import read_docx


def _call(prompt: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY", "")
    _gc._client_manager.configure(api_key=api_key)
    _gc._client_manager.clients = {}
    model = genai.GenerativeModel(GEMINI_MODEL)
    response = model.generate_content(prompt)
    return response.text.strip()


def _parse_json_block(text: str) -> dict:
    """Extract JSON from a response that may wrap it in markdown code fences."""
    match = re.search(r'```(?:json)?\s*([\s\S]+?)\s*```', text)
    raw = match.group(1) if match else text
    return json.loads(raw)


# ── Draft generation (Step 1 of 2) ───────────────────────────────────────────

def generate_draft(
    company_name: str,
    tier: int,
    clusters: list,
    banner_count: int,
    posts_count: str,
    extra_context: str,
) -> dict:
    """
    Given company info + any optional extra context the user typed,
    ask the LLM to produce:
      - portfolio_name
      - fest_deliverables
      - company_deliverables
      - brand_event_description  (empty string if tier != 1)
      - questions  (list of strings — clarifying questions the LLM needs
                    answered before it can improve its output; empty list if none)

    Returns a dict with those five keys.
    """
    guidelines    = read_docx("guidelines/portfolio_name_guidelines.docx")
    fest_doc      = read_docx("deliverables/deliverables_from_fest.docx")
    company_doc   = read_docx("deliverables/deliverables_from_company.docx")
    branding_doc  = read_docx("guidelines/branding_informal_events.docx") if tier == 1 else ""

    clusters_str = ", ".join(clusters)
    brand_section = (
        "- brand_event_description: a SHORT description (max 2 sentences, ~40 words total) of a brand "
        "engagement event on the Festember informal stage, specific to this company's industry. "
        "Keep it tight — the slide text box is small and longer text overflows."
        if tier == 1 else
        "- brand_event_description: empty string (not applicable for this tier)"
    )

    extra_block = (
        f"\nExtra context provided by the user about this company:\n{extra_context}\n"
        if extra_context.strip() else ""
    )

    prompt = f"""You are helping Festember's Media & Reach (FMR) team draft a sponsorship proposal for:

Company: {company_name}
Tier: {tier}
Clusters: {clusters_str}
Banners per cluster: {banner_count}
Digital posts: {posts_count}
{extra_block}
--- REFERENCE DOCUMENTS ---

Portfolio name guidelines:
{guidelines}

Deliverables Festember offers (past proposals):
{fest_doc}

Deliverables we expect from companies (past proposals):
{company_doc}
{f"Brand engagement event formats:{chr(10)}{branding_doc}" if branding_doc else ""}

--- TASK ---

Produce a JSON object with exactly these keys:
{{
  "portfolio_name": "<single creative name, no quotes or punctuation>",
  "fest_deliverables": "<bullet-point list of what Festember will provide — see rules below>",
  "company_deliverables": "<bullet-point list of what the company provides — see rules below>",
  {brand_section},
  "questions": [
    "<question 1 if you need more info to improve the proposal>",
    "<question 2 ...>"
  ]
}}

Deliverable rules (STRICTLY follow these):
- Every deliverable must be fully quantified. No vague items.
  - Ads: specify duration (e.g. 30-second) and frequency (e.g. 3 times per day)
  - Social media posts: specify exact count (e.g. 3 Instagram posts + 2 stories)
  - Articles/press: specify count and platform
  - Email campaigns: specify number of sends and estimated reach
- Banners and standees from Festember: state a SINGLE combined total (max 6 combined, e.g. "4 banners and 2 standees across the fest venue"). Do NOT break this down per cluster — the total is across all clusters combined. This number is negotiable but start at or below 6 combined.
- Do not invent deliverables that are not grounded in the reference documents or the company's industry.
- questions must be a JSON array. If you have no questions, use [].
- Only ask questions that would meaningfully change the deliverables (e.g. specific product lines, target audience, past association with events). Do NOT ask for information already given.
- Return ONLY the JSON object. No markdown, no explanation."""

    raw = _call(prompt)
    try:
        data = _parse_json_block(raw)
    except (json.JSONDecodeError, AttributeError):
        data = {
            "portfolio_name": "",
            "fest_deliverables": raw,
            "company_deliverables": "",
            "brand_event_description": "",
            "questions": [],
        }

    def _to_str(val) -> str:
        if isinstance(val, list):
            return "\n".join(f"• {item}" for item in val if item)
        return str(val) if val else ""

    data["portfolio_name"]          = _to_str(data.get("portfolio_name", ""))
    data["fest_deliverables"]       = _to_str(data.get("fest_deliverables", ""))
    data["company_deliverables"]    = _to_str(data.get("company_deliverables", ""))
    data["brand_event_description"] = _to_str(data.get("brand_event_description", ""))
    if not isinstance(data.get("questions"), list):
        data["questions"] = []
    data["questions"] = [str(q) for q in data["questions"]]

    return data


# ── Reformat free-flow deliverable text into clean bullet points ──────────────

def reformat_deliverables(raw_text: str, label: str) -> str:
    """Take free-flow user text and return clean, quantified bullet points."""
    if not raw_text.strip():
        return raw_text
    prompt = f"""You are editing a sponsorship proposal deliverable list for Festember, a college cultural fest.

The user has written the following in free-flow text for "{label}":
---
{raw_text}
---

Reformat this into clean, professional bullet points (use "• " prefix for each bullet).
Rules:
- Preserve all the user's intended content — do not add or remove deliverables.
- Every item must be fully quantified: ads must have duration and frequency, social media must have counts, banners/standees must have total numbers.
- Fix grammar, punctuation, and formatting only.
- Return ONLY the reformatted bullet list. No explanation, no preamble."""
    try:
        return _call(prompt).strip()
    except Exception:
        return raw_text


# ── Structure company deliverables into 4 slide categories ───────────────────

def structure_company_deliverables(company_deliverables: str, company_name: str) -> list:
    """
    Categorize company deliverables into 4 sections matching the PPT slide layout.

    The slide has 4 fixed section slots:
      1. SOCIAL MEDIA MARKETING (fixed heading)
      2. GOODIES (fixed heading)
      3. Custom heading
      4. Custom heading

    Returns a list of (heading, items_text) tuples — up to 4 entries.
    items_text is a newline-separated bullet list.
    """
    if not company_deliverables.strip():
        return []

    prompt = f"""You are organizing sponsorship deliverables from {company_name} into 4 categories for a PPT slide.

The deliverables are:
{company_deliverables}

Organize these into EXACTLY 4 sections. Use these fixed names for sections 1 and 2:
  1. "SOCIAL MEDIA MARKETING" — all social media posts, stories, collaborations, digital promotions
  2. "GOODIES" — merchandise, discounts, vouchers, gifts, subscription offers, free samples

For sections 3 and 4, choose appropriate SHORT names (2-4 words, ALL CAPS) for the remaining deliverables.
If fewer than 4 natural categories exist, combine minor items and leave a section as empty.

Return ONLY a JSON array like:
[
  {{"heading": "SOCIAL MEDIA MARKETING", "items": ["• item1", "• item2"]}},
  {{"heading": "GOODIES", "items": ["• item1"]}},
  {{"heading": "ADS & PROMOTIONS", "items": ["• item1", "• item2"]}},
  {{"heading": "LIVE ACTIVATIONS", "items": ["• item1"]}}
]

Rules:
- Each item must start with "• "
- Keep all content from the original deliverables — do not omit or invent items
- If a section has no items, use an empty list []
- Return ONLY the JSON array, no explanation"""

    try:
        raw = _call(prompt)
        sections_data = _parse_json_block(raw)
        if not isinstance(sections_data, list):
            raise ValueError("LLM did not return a list")
        result = []
        for s in sections_data[:4]:
            heading = str(s.get("heading", "")).strip()
            items = s.get("items", [])
            if isinstance(items, list):
                items_text = "\n".join(str(i) for i in items if i)
            else:
                items_text = str(items)
            result.append((heading, items_text))
        return result
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("structure_company_deliverables failed: %s", exc)
        # Fallback: dump everything into section 1, leave others empty
        return [
            ("SOCIAL MEDIA MARKETING", company_deliverables),
            ("GOODIES", ""),
            ("ACTIVATIONS", ""),
            ("OTHER BENEFITS", ""),
        ]


# ── CSR event auto-generation ─────────────────────────────────────────────────

def generate_csr_event(company_name: str, portfolio_name: str) -> str:
    """
    Generate a concise CSR event description for the CSR slide.
    Returns 1-2 sentences describing an appropriate CSR activity.
    """
    prompt = f"""You are writing a Corporate Social Responsibility event description for a sponsorship proposal.

Company: {company_name}
Their association with Festember: {portfolio_name}

Suggest ONE brief, realistic CSR activity that {company_name} could co-host with Festember's Social Responsibility Team (FSR) at NIT Trichy. It should be:
- Relevant to the company's industry or brand values
- Simple and feasible (e.g., blood donation camp, tree plantation, book/stationery donation, digital literacy workshop, hygiene kit distribution)
- 1-2 sentences maximum

Return ONLY the event description. No preamble, no explanation."""
    try:
        return _call(prompt).strip()
    except Exception:
        return (
            f"A community welfare drive will be co-hosted by {company_name} and "
            "Festember's Social Responsibility Team on the NIT Trichy campus, "
            "engaging students and faculty in giving back to the local community."
        )


# ── Cover letter (used after user confirms deliverables) ──────────────────────

def generate_cover_letter(
    company_name: str,
    tier: int,
    portfolio_name: str,
    fest_deliverables: str,
    company_deliverables: str,
    manager_name: str,
    manager_designation: str,
    manager_phone: str = "",
    manager_email: str = "",
) -> str:
    cover_template = read_docx("templates/cover_letter_template.docx")
    contact_line = manager_name
    if manager_designation:
        contact_line += f", {manager_designation}"
    if manager_phone:
        contact_line += f" | {manager_phone}"
    if manager_email:
        contact_line += f" | {manager_email}"

    prompt = f"""You are writing a cover letter for a sponsorship proposal email to {company_name}.

Portfolio name: {portfolio_name}
Tier: {tier}
What Festember offers:
{fest_deliverables}

What we ask from them:
{company_deliverables}

Our contact:
{contact_line}

Cover letter template:
{cover_template}

Fill in the template for this company. Keep the structure. Replace variable parts with specifics. Professional, concise, warm tone.
At the end of the letter, include the contact details exactly as: {contact_line}
Return only the letter text."""
    return _call(prompt)
