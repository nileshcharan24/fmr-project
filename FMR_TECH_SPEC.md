# FMR Automation Platform — Technical Specification
If it is better to use a virtual environment, do that. Cuz i dont want to mess things up. But at the end ensure that i can deploy this and everyone can use it.

## Tech Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Backend language | Python | 3.11+ | All server logic |
| Backend framework | FastAPI | 0.111+ | REST API, file handling, async |
| Database | SQLite | Built-in | User data, proposals, rate limits |
| ORM/DB driver | sqlite3 | Built-in | Direct SQL queries (no ORM) |
| LLM | Google Gemini 1.5 Flash | Latest | All text generation tasks |
| LLM SDK | google-generativeai | 0.8+ | Python SDK for Gemini |
| PPTX editing | python-pptx + XML scripts | 0.6.23+ | Template manipulation |
| DOCX reading | python-docx | 1.1+ | Read resource Word docs as text |
| Auth | python-jose + passlib | Latest | JWT tokens, password hashing |
| Env vars | python-dotenv | Latest | Load .env file |
| Frontend | React + Vite | React 18 | User interface |
| HTTP client | axios | Latest | Frontend API calls |
| UI styling | TailwindCSS | 3.x | Simple, clean styling |
| Dev server | uvicorn | Latest | FastAPI ASGI server |

---

## Complete File Structure

```
fmr-automation/
│
├── .env                              ← NEVER COMMIT. Contains secrets.
├── .gitignore                        ← Ignore .env, outputs/, database/, __pycache__/
├── README.md
│
├── FMR_PROJECT_PLAN.md               ← DO NOT EDIT. Reference only.
├── FMR_TECH_SPEC.md                  ← DO NOT EDIT. Reference only.
│
├── requirements.txt                  ← All Python dependencies
│
├── resources/                        ← Admin uploads files here. READ-ONLY for the app.
│   ├── templates/
│   │   └── sponsorship_proposal.pptx ← Master PPT template (admin uploads)
│   ├── deliverables/
│   │   ├── deliverables_from_fest.docx
│   │   └── deliverables_from_company.docx
│   ├── guidelines/
│   │   ├── portfolio_name_guidelines.docx
│   │   └── branding_informal_events.docx
│   └── clusters/
│       └── cluster_descriptions.json ← { "Music": "desc...", "Film": "desc..." }
│
├── outputs/                          ← Generated files. Created at runtime.
│   └── {username}/
│       └── {company}_{timestamp}/
│           ├── proposal.pptx
│           └── cover_letter.txt
│
├── database/
│   └── fmr.db                        ← SQLite DB. Created at runtime.
│
├── temp/                             ← Temp working dir for PPT generation. Cleaned after each run.
│
├── backend/
│   ├── main.py                       ← FastAPI app, CORS, router registration, startup events
│   ├── config.py                     ← All constants and env var loading
│   ├── database.py                   ← DB connection, table creation, query helpers
│   ├── auth.py                       ← JWT creation/validation, password hashing, auth middleware
│   │
│   ├── routes/
│   │   ├── auth_routes.py            ← POST /auth/login, GET /auth/me
│   │   ├── proposal_routes.py        ← POST /proposals/generate, GET /proposals/, downloads
│   │   └── admin_routes.py           ← User management, resource management, all proposals
│   │
│   ├── services/
│   │   ├── llm.py                    ← All Gemini API calls, one function per task
│   │   ├── pptx_editor.py            ← Full PPT pipeline (unpack → edit → pack)
│   │   ├── resource_reader.py        ← Read .docx files as text, read JSON resources
│   │   └── rate_limiter.py           ← Check and increment weekly usage per user
│   │
│   └── scripts/                      ← PPTX skill scripts (copied from skill, do not modify)
│       ├── office/
│       │   ├── unpack.py
│       │   └── pack.py
│       ├── add_slide.py
│       └── clean.py
│
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── tailwind.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx                   ← Routes: /login, /dashboard, /generate, /outputs, /admin
        ├── api.js                    ← Axios instance with base URL and auth header
        ├── context/
        │   └── AuthContext.jsx       ← JWT storage, login/logout, current user
        ├── pages/
        │   ├── Login.jsx
        │   ├── Dashboard.jsx
        │   ├── GenerateProposal.jsx
        │   ├── MyOutputs.jsx
        │   └── AdminPanel.jsx
        └── components/
            ├── ProtectedRoute.jsx    ← Redirect to login if no token
            ├── AdminRoute.jsx        ← Redirect if not admin
            ├── RateLimitBadge.jsx    ← Shows "2/3 used this week"
            ├── ProposalForm.jsx      ← The main generation form
            ├── OutputCard.jsx        ← Card for each past proposal
            └── ResourceManager.jsx   ← Admin file upload/list component
```

---

## Key Constants (config.py)

```python
# Tier-based rules
TIER_CLUSTERS = {1: (3, 5), 2: (2, 3), 3: (1, 1)}        # (min, max) clusters
TIER_BANNERS  = {1: (3, 4), 2: (2, 2), 3: (1, 1)}         # (min, max) banners per cluster
TIER_POSTS    = {1: "2 posts and stories", 2: "1-2 posts and a story", 3: "1 post and story"}

# Slides to DELETE based on tier
SLIDES_TIER_1_ONLY = [10, 13, 14]   # Delete these for Tier 2 and 3
SLIDES_TIER_1_2    = [15]            # Delete for Tier 3 (CSR — optional for Tier 2)

# Cluster slide index (1-based, from original template)
CLUSTER_SLIDE_INDEX = 12

# Logo placement on Slide 5 (tune after viewing template)
LOGO_SLIDE_INDEX = 5
LOGO_LEFT_INCHES = 4.5
LOGO_TOP_INCHES  = 2.8
LOGO_WIDTH_INCHES = 2.5

# Outreach defaults
OUTREACH_EVENT = ["Gigahertz", "Festember football league", "rolling reels film festival"]
OUTREACH_CITIES = ["Bangalore", "Chennai", "Pondicherry"]

# Rate limit
WEEKLY_LIMIT = 3

# Paths
RESOURCES_DIR  = "resources"
OUTPUTS_DIR    = "outputs"
TEMP_DIR       = "temp"
DATABASE_PATH  = "database/fmr.db"
TEMPLATE_PPTX  = "resources/templates/sponsorship_proposal.pptx"
```

---

## Database Schema

```sql
-- Users
CREATE TABLE IF NOT EXISTS users (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  username    TEXT    UNIQUE NOT NULL,
  password_hash TEXT  NOT NULL,
  role        TEXT    NOT NULL DEFAULT 'user',  -- 'user' or 'admin'
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Proposals (one row per generation run)
CREATE TABLE IF NOT EXISTS proposals (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id       INTEGER NOT NULL,
  company_name  TEXT    NOT NULL,
  tier          INTEGER NOT NULL,
  clusters      TEXT    NOT NULL,  -- JSON array string: '["Music","Film"]'
  output_folder TEXT    NOT NULL,
  status        TEXT    DEFAULT 'pending',  -- 'pending', 'done', 'failed'
  error_message TEXT,
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(user_id) REFERENCES users(id)
);

-- Rate limits (one row per user per week)
CREATE TABLE IF NOT EXISTS rate_limits (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id     INTEGER NOT NULL,
  week_string TEXT    NOT NULL,  -- e.g. "2025-W19"
  count       INTEGER DEFAULT 0,
  UNIQUE(user_id, week_string),
  FOREIGN KEY(user_id) REFERENCES users(id)
);
```

---

## API Reference

### Auth
```
POST   /auth/login          { username, password } → { token, role }
GET    /auth/me             → { id, username, role }
```

### Proposals (requires JWT)
```
POST   /proposals/generate             multipart/form-data → { proposal_id, cover_letter, portfolio_name }
GET    /proposals/                     → list of user's proposals
GET    /proposals/{id}/status          → { status, error_message }
GET    /proposals/{id}/download/ppt    → file download (proposal.pptx)
GET    /proposals/{id}/cover-letter    → { cover_letter: "text..." }
GET    /proposals/rate-limit           → { used, limit, resets_on }
```

### Admin (requires JWT + admin role)
```
POST   /admin/users                       { username, password, role } → created user
GET    /admin/users                       → all users
DELETE /admin/users/{id}                  → deleted
POST   /admin/users/{id}/reset-rate-limit → reset this week's count

POST   /admin/resources/upload     multipart (file) → saved path
GET    /admin/resources            → list of files with name, type, size, modified
GET    /admin/resources/{filename} → file download
DELETE /admin/resources/{filename} → deleted

GET    /admin/resources/clusters     → cluster_descriptions.json contents
PUT    /admin/resources/clusters     { "Music": "desc...", ... } → saved

GET    /admin/proposals              → all proposals across all users
```

---

## PPT Editing — Detailed Implementation Notes

### Why XML approach (not python-pptx alone)
The template uses free text boxes (not PowerPoint placeholders). `python-pptx` cannot reliably find/replace in free text boxes when text is split across multiple `<a:r>` runs. The XML approach reads raw slide files and does direct string replacement, which is more reliable.

### Text Replacement Function
```python
import re

def replace_placeholders(xml_text: str, replacements: dict) -> str:
    """
    replacements = {
      "company": "The Hindu",
      "portfolio": "The Spectacle",
      ...
    }
    Handles all case variants: <company>, <Company>, <COMPANY>, <COMPANY NAME>, etc.
    """
    for key, value in replacements.items():
        # Match <key>, <Key>, <KEY>, and space variants like <company name>
        pattern = re.compile(
            rf'<{re.escape(key)}(\s+\w+)*>',
            re.IGNORECASE
        )
        xml_text = pattern.sub(value, xml_text)
    return xml_text
```

Apply this to every slide XML file after structural changes are complete.

### Slide Deletion Order
When deleting multiple slides, always delete from highest index to lowest to avoid index shifting. After all deletions, run `clean.py` once.

### Cluster Slide Duplication
Use `add_slide.py` to duplicate the cluster slide (index 12) N-1 additional times for N total clusters. Update each duplicated slide with a different cluster's data.

### Logo Insertion
After `pack.py` creates the output PPTX, use `python-pptx` to:
1. Load output PPTX
2. Access slide at `LOGO_SLIDE_INDEX - 1` (0-based)
3. Call `slide.shapes.add_picture(logo_path, left, top, width)` using inch values from config
4. Save back to same path

---

## LLM Prompt Templates

### Portfolio Name
```
You are helping FMR (Festember Media & Reach) generate a creative portfolio name for a company sponsorship.

Company: {company_name}
Tier: {tier}

Guidelines and examples:
{portfolio_name_guidelines_text}

Return ONLY the portfolio name. No explanation, no punctuation, no quotes. Just the name.
```

### Fest Deliverables (what Festember offers)
```
You are drafting deliverables for a non-monetary barter sponsorship proposal for {company_name} (Tier {tier}).

Clusters selected: {clusters_list}
Banners per cluster: {banner_count}
Digital posts: {posts_count}

Reference deliverables from past proposals:
{deliverables_from_fest_text}

Generate a clean bullet-point list of what Festember will provide to this company. Be specific and professional. Max 8 bullets. No fluff.
```

### Company Deliverables (what they give us)
```
You are drafting what {company_name} (Tier {tier}) will provide to Festember as part of a non-monetary barter sponsorship.

Reference:
{deliverables_from_company_text}

Generate a clean bullet-point list of what we expect from this company. Realistic, professional. Max 6 bullets grouped by category (social media, goodies, etc.).
```

### Brand Event Description (Tier 1 only)
```
Generate a 2-3 sentence description of a brand engagement event that Festember will host for {company_name} on the informal stage or college grounds.

Reference events and formats:
{branding_informal_events_text}

Be specific to this company's industry. Professional tone.
```

### Cover Letter
```
You are writing a cover letter for a sponsorship proposal email to {company_name}.

Portfolio name: {portfolio_name}
Tier: {tier}
What Festember offers:
{fest_deliverables}

What we ask from them:
{company_deliverables}

Cover letter template:
{cover_letter_template_text}

Fill in the template for this company. Keep the structure. Replace variable parts with specifics. Professional, concise, warm tone. Return only the letter text.
```

---

## Frontend Form Fields

```
GenerateProposal.jsx form fields:

Required:
- company_name: text input
- tier: radio buttons (Tier 1 / Tier 2 / Tier 3) with tooltip showing size guide
- clusters: checkbox list (loaded from /admin/resources/clusters)
- logo: file upload (PNG/JPG, max 5MB)
- manager_name: text
- manager_designation: dropdown ("Media Manager" / "Deputy Media Manager")
- manager_phone: text
- manager_email: email

Optional:
- custom_notes: textarea ("Any specific notes for the AI?")
- include_csr: checkbox (only shown for Tier 2)
- outreach_city: dropdown (only shown for Tier 1) — ["Bangalore", "Chennai", "Pondicherry"]

Auto-filled / shown to user:
- Banner count: shown below tier selection ("Tier 1 → 3-4 banners per cluster")
- Excluded slides: shown below tier ("Slides not included for this tier: Pronite, Brand Engagement, Outreach")
```

---

## Environment Variables (.env)

```
# Required
GEMINI_API_KEY=AIzaSyCRXvX7Cq01LfYjEHLA2tw9BAeNR_5KtwQ
JWT_SECRET=long_random_string_for_signing_tokens

# Admin credentials (used on first run to seed admin user)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin

# Optional
PORT=8000
FRONTEND_URL=http://localhost:5173
```

---

## requirements.txt

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
python-multipart==0.0.9
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-dotenv==1.0.1
google-generativeai==0.8.3
python-pptx==0.6.23
python-docx==1.1.2
defusedxml==0.7.1
aiofiles==23.2.1
```

---

## Claude Code Prompt — Initial Setup

Copy this entire prompt and give it to Claude Code to begin building the project:

```
You are building the FMR Automation Platform. This is a web app for the Festember Media & Reach team to auto-generate sponsorship proposal PPTs and cover letters using Gemini 1.5 Flash.
If it is better to use a virtual environment, do that. Cuz i dont want to mess things up. But at the end ensure that i can deploy this and everyone can use it.

Your two reference documents are:
- FMR_PROJECT_PLAN.md — full project description, workflow, slide logic, and phased build steps
- FMR_TECH_SPEC.md — complete file structure, tech stack, API reference, DB schema, constants

RULES:
1. Read BOTH reference documents fully before writing any code.
2. Never edit FMR_PROJECT_PLAN.md or FMR_TECH_SPEC.md.
3. Build one phase at a time. Do not start the next phase until the current one is confirmed working.
4. When you need the human to do something (install tools, add API keys, place files), STOP and print a clear numbered list of steps. Wait for confirmation before continuing.
5. Always read the PPTX skill at /mnt/skills/public/pptx/SKILL.md and /mnt/skills/public/pptx/editing.md before building Phase 4.
6. All credentials must come from .env — never hardcode.
7. After each phase, print a short test checklist so the human can verify it works before you proceed.

START with Phase 0 verification:
- Check if .env exists and has required keys
- Check if resource files are in the correct folders
- Print exactly what is present and what is missing
- If anything is missing, print what the human needs to do and STOP

Then proceed to Phase 1: Backend Foundation.
```

---

## Deployment Notes (When Ready)

**Local development:**
```bash
# Backend
cd backend
pip install -r ../requirements.txt
uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

**Railway deployment (free tier):**
- Deploy backend as Python service
- Deploy frontend as static site (after `npm run build`)
- Set all env vars in Railway dashboard
- SQLite DB will reset on redeploy — export/import if needed, or upgrade to Railway's Postgres

**Domain:** Railway gives a free subdomain. Share that URL with your 30-person team.

At any point, feel free to stop me, ask questions, give me dimple instruction steps if i have to do anything. And after each prompt, tell me what is built and how i can test it. Im dont know coding so keep that in mind.