# FMR Automation Platform — Project Plan

## What This Is
A web app for FMR (Festember Media & Reach) team members to auto-generate sponsorship proposal PPTs and cover letters for media companies. Contacts are still found manually. The app centralises resources, enforces rate limits, and stores all outputs.

---

## Users & Roles

| Role | What They Do |
|------|-------------|
| Admin | Upload and manage all resources, manage users, view all outputs |
| User (Manager/Junior) | Fill proposal form, generate PPT + cover letter, download outputs |

---

## Full Workflow

### User's Journey (One Proposal Cycle)

1. User logs in
2. Fills form:
   - Company name
   - Tier (1, 2, or 3) — user selects based on company size
   - Clusters to associate (checkbox list — pulled from resources)
   - Number of banners/standees per cluster (auto-filled by tier, user can override)
   - Upload company logo (PNG/JPG)
   - Manager name, designation (Media Manager / Deputy Media Manager), phone, email
   - Any custom notes for deliverables (optional)
3. Clicks "Generate"
4. Backend pipeline runs:
   - Gemini Flash generates: portfolio name, deliverables list (from company + from Festember), brand event description (Tier 1 only), cover letter
   - Python XML pipeline edits the PPTX template
5. User sees output: PPT download + cover letter text (copy-paste ready)
6. User edits manually as needed (PPT is fully editable)
7. All outputs saved — user can retrieve them later

### Admin's Journey

1. Logs in with admin credentials
2. Uploads/replaces resource files (word docs, PPTX template) at any time
3. Edits cluster descriptions via simple UI (stored as JSON)
4. Views all generated proposals by user/date
5. Manages users (add, remove, reset rate limit if needed)

---

## Resource Files (Admin Uploads These)

```
resources/
├── templates/
│   └── sponsorship_proposal.pptx       ← Master PPTX template
├── deliverables/
│   ├── deliverables_from_fest.docx      ← What Festember offers companies
│   └── deliverables_from_company.docx   ← What we ask from companies
├── guidelines/
│   ├── portfolio_name_guidelines.docx   ← Rules + examples for naming
│   └── branding_informal_events.docx    ← Brand engagement event descriptions
└── clusters/
    └── cluster_descriptions.json        ← Cluster name → description mapping
```

The LLM reads these files as context for generation. Admin edits them via the admin panel. The PPTX template is replaced via admin upload.

---

## PPT Template Slide Logic

Slides use free text boxes with string placeholders like `<company>`, `<Company>`, `<COMPANY>`, `<portfolio>`, `<Portfolio>`, etc. The pipeline does case-insensitive find-and-replace across all XML.

### Slide-by-Slide Rules

| Slide | Content | Tier Rule | Placeholders |
|-------|---------|-----------|-------------|
| All slides | Company name, portfolio | All tiers | `<company>`, `<Company>`, `<COMPANY>`, `<portfolio>`, `<Portfolio>` |
| Slide 5 | Company logo | All tiers | Logo image inserted into defined region |
| Slide 10 | Pronite partnership | Tier 1 ONLY — delete for Tier 2 & 3 | `<company>` |
| Slide 12 | Cluster association | All tiers — **duplicate this slide per cluster** | `<company>`, `<cluster>`, `<banners>`, `<cluster_description>` |
| Slide 13 | Brand engagement | Tier 1 ONLY — delete for Tier 2 & 3 | `<company>`, `<banners>`, `<event_description>` |
| Slide 14 | Outreach association | Tier 1 ONLY — delete for Tier 2 & 3 | `<company>`, `<event>` (Gigahertz), `<city>` (Bangalore/Chennai/Pondicherry) |
| Slide 15 | CSR | Tier 1 (always), Tier 2 (optional — admin can toggle) — delete for Tier 3 | `<company>`, `<portfolio>`, `<event_description>` |
| Slide 16 | Digital marketing | All tiers | `<company>`, `<posts_count>` |
| Slide 18 | Deliverables from company | All tiers | `<deliverables_list>` |
| Slide 20 | Manager contact details | All tiers | `<name>`, `<designation>`, `<phone>`, `<email>` |

### Tier-Based Auto Values

| Field | Tier 1 | Tier 2 | Tier 3 |
|-------|--------|--------|--------|
| Clusters | 3–5 | 2–3 | 1 |
| Banners/standees per cluster | 3–4 | 2 | 1 |
| Posts (Slide 16) | 2 posts + stories | 1–2 posts + story | 1 post + story |
| Slide 10 (Pronite) | Include | Delete | Delete |
| Slide 13 (Brand engagement) | Include | Delete | Delete |
| Slide 14 (Outreach) | Include | Delete | Delete |
| Slide 15 (CSR) | Include | Optional | Delete |

---

## LLM Tasks (Gemini 1.5 Flash)

All prompts are structured with resource file content as context. Each call is short and focused.

| Task | Prompt Input | Output |
|------|-------------|--------|
| Portfolio name | Company name + tier + portfolio guidelines doc | Short string (e.g. "The Spectacle") |
| Deliverables from Festember | Company name + tier + clusters chosen + festember deliverables doc + tier values | Bullet list |
| Deliverables from company | Company name + tier + company deliverables doc | Bullet list |
| Brand event description | Company name + branding doc | 2–3 sentence description |
| Cover letter | Company name + tier + portfolio + cover letter template + all generated deliverables | Full text |

Gemini 1.5 Flash is used via Google AI Studio free API (no billing until quota exceeded). Rate: 1500 requests/day free.

---

## Rate Limiting

- Each user: max 3 proposal generations per week (Mon 00:00 to Sun 23:59)
- Admin can manually reset a user's count
- If limit hit: show "You've used 3/3 proposals this week. Resets Monday." — no generation allowed
- Tracked in SQLite: `user_id, week_string (e.g. "2025-W19"), count`

---

## Output Storage

```
outputs/
└── {username}/
    └── {company_name}_{timestamp}/
        ├── proposal.pptx
        └── cover_letter.txt
```

Users see a "Previous Outputs" list on their dashboard. Click to re-download any past output. Admin sees all outputs.

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | Python + FastAPI | Simple, fast, great for file handling |
| Frontend | React + Vite | Clean UI, easy form handling |
| Database | SQLite | Zero setup, sufficient for 30 users |
| LLM | Google Gemini 1.5 Flash API | Free tier, fast, sufficient quality |
| PPT editing | XML manipulation (unpack → edit → repack) | Only reliable method for free-text-box PPTX |
| File storage | Local filesystem | No cost, simple |
| Auth |Use google OAuth | Simple username/password with JWT |
| Hosting | Local or Railway free tier | Start local, deploy if needed |

---

## Build Phases

---

### PHASE 0 — Human Setup (many of these are done. if not done, i will mention and ask you to verify them and do them by putting - (claude verify))

**Stop. Do these before Claude Code starts building.**

1. **Get Gemini API key:**
   - Go to https://aistudio.google.com/app/apikey
   - Create a free API key
   - Copy it — you'll add it to `.env`

2. **Prepare resource files:**
   - Collect all your Word docs and the PPTX template
   - Name them exactly: `sponsorship_proposal.pptx`, `deliverables_from_fest.docx`, `deliverables_from_company.docx`, `portfolio_name_guidelines.docx`, `branding_informal_events.docx`

3. **Create cluster_descriptions.json manually:**
   ```json
   {
     "Music": "Description of music cluster and its events...",
     "Film": "Description of film cluster...",
     "Dance": "Description of dance cluster...",
     "etc": "..."
   }
   ```
   Save it as `cluster_descriptions.json`

4. (Claude verify) **Install prerequisites on your machine:**
   - Python 3.11+: https://python.org
   - Node.js 20+: https://nodejs.org
   - Git: https://git-scm.com

5. **Create project folder:**
   ```bash
   mkdir FMR_Project
   cd FMR_Project
   git init
   ```

I changed the root folder name. from now on follow this everywhere.

6. **Create `.env` file** in project root:
   ```
   GEMINI_API_KEY=your_key_here
   JWT_SECRET=any_random_long_string_here
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD=choose_a_secure_password
   ```

7. **Place resource files** into:
   ```
   fmr-automation/resources/templates/sponsorship_proposal.pptx
   fmr-automation/resources/templates/cover_letter_template.docx
   fmr-automation/resources/deliverables/deliverables_from_fest.docx
   fmr-automation/resources/deliverables/deliverables_from_company.docx
   fmr-automation/resources/guidelines/portfolio_name_guidelines.docx
   fmr-automation/resources/guidelines/branding_informal_events.docx
   fmr-automation/resources/clusters/cluster_descriptions.json
   ```

**Once done, hand control to Claude Code with Phase 1.**

---

### PHASE 1 — Backend Foundation

**Goal:** Working FastAPI app with database, auth, and file structure.

**Build:**
- `backend/main.py` — FastAPI app entry point
- `backend/database.py` — SQLite setup using `sqlite3`. Tables: `users`, `proposals`, `rate_limits`
- `backend/auth.py` — Login endpoint, JWT token generation/validation, middleware
- `backend/config.py` — Load `.env` vars, define constants (TIERS, SLIDE_RULES, BANNER_COUNTS, etc.)
- Project-level folder structure creation on startup: `resources/`, `outputs/`, `database/`
- `requirements.txt` — all Python dependencies

**Database schema:**
```sql
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user',   -- 'user' or 'admin'
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE proposals (
  id INTEGER PRIMARY KEY,
  user_id INTEGER,
  company_name TEXT,
  tier INTEGER,
  output_folder TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE rate_limits (
  id INTEGER PRIMARY KEY,
  user_id INTEGER,
  week_string TEXT,   -- e.g. "2025-W19"
  count INTEGER DEFAULT 0,
  FOREIGN KEY(user_id) REFERENCES users(id)
);
```

**API endpoints this phase:**
- `POST /auth/login` → returns JWT
- `GET /auth/me` → returns current user info
- `POST /admin/users` → create user (admin only)
- `GET /admin/users` → list all users (admin only)
- `DELETE /admin/users/{id}` → delete user (admin only)
- `POST /admin/rate-limit/reset/{user_id}` → reset weekly count

**Expected output:** Backend runs on `localhost:8000`. Login works. Admin can create user accounts.

---

### PHASE 2 — Resource Management (Admin)

**Goal:** Admin can upload, view, and replace resource files via API.

**Build:**
- `backend/routes/admin.py` — resource management endpoints
- `backend/services/resource_reader.py` — utility to read `.docx` files as plain text (use `python-docx`), read JSON files, list available resources

**API endpoints this phase:**
- `POST /admin/resources/upload` — upload a resource file (multipart form). Overwrites if same name exists. Validates file type.
- `GET /admin/resources` — list all resource files with name, type, last modified
- `GET /admin/resources/{filename}` — download a resource file
- `DELETE /admin/resources/{filename}` — delete a resource file
- `GET /admin/resources/clusters` — return parsed cluster_descriptions.json
- `PUT /admin/resources/clusters` — update cluster descriptions (JSON body)

**Expected output:** Admin can manage all resource files via API calls. Claude Code should test by uploading a dummy file and verifying it appears in the list.

---

### PHASE 3 — LLM Integration (Gemini)

**Goal:** Given company info + resource files, Gemini generates all text content.

**Build:**
- `backend/services/llm.py` — all Gemini calls, using `google-generativeai` SDK
- One function per LLM task (portfolio name, fest deliverables, company deliverables, brand event description, cover letter)
- Each function: reads relevant resource files → builds prompt → calls Gemini 1.5 Flash → returns clean string

**Function signatures:**
```python
def generate_portfolio_name(company_name: str, tier: int) -> str
def generate_fest_deliverables(company_name: str, tier: int, clusters: list[str], banner_count: int) -> str
def generate_company_deliverables(company_name: str, tier: int) -> str
def generate_brand_event_description(company_name: str) -> str  # Tier 1 only
def generate_cover_letter(company_name: str, tier: int, portfolio: str, fest_deliverables: str, company_deliverables: str) -> str
```

**Prompt rules:**
- Always include relevant resource file content in the prompt as context
- Instruct model to be concise and professional (PPT format)
- For deliverables: return as bullet points, max 6 per category
- For portfolio name: return ONLY the name, no explanation
- For cover letter: follow the template structure exactly, only fill in the variable parts

**Expected output:** Call each function with test data and verify output is clean, well-formatted, and appropriate.

---

### PHASE 4 — PPT Generation Pipeline

**Goal:** Given all inputs + LLM outputs, produce a final edited PPTX.

**Build:**
- Copy PPTX skill scripts into `backend/scripts/office/` (unpack.py, pack.py, add_slide.py, clean.py)
- `backend/services/pptx_editor.py` — main PPT pipeline

**Pipeline steps in `pptx_editor.py`:**

```
1. Copy template PPTX to temp working dir
2. Run unpack.py → get unpacked/ folder
3. Read ppt/presentation.xml to get slide ID list
4. STRUCTURAL CHANGES (before any content edits):
   a. If Tier 2 or 3: delete Slide 10 (pronite)
   b. If Tier 2 or 3: delete Slide 13 (brand engagement)
   c. If Tier 2 or 3: delete Slide 14 (outreach)
   d. If Tier 3: delete Slide 15 (CSR)
   e. Duplicate Slide 12 (cluster) N-1 times where N = number of clusters chosen
   f. Run clean.py after deletions
5. CONTENT EDITS (slide by slide):
   a. All slides: replace all variants of <company>, <Company>, <COMPANY> with company_name
   b. All slides: replace all variants of <portfolio>, <Portfolio> with portfolio_name
   c. Slide 5: insert company logo image
   d. Cluster slides (one per cluster): fill cluster name, banner count, cluster description
   e. Slide 13 (if kept): fill brand event description, banner count
   f. Slide 14 (if kept): fill event name (Gigahertz), city
   g. Slide 15 (if kept): fill CSR event description
   h. Slide 16: fill posts count
   i. Slide 18: fill company deliverables bullet list
   j. Slide 20: fill manager name, designation, phone, email
6. Run pack.py → output.pptx
7. Move output.pptx to outputs/{username}/{company}_{timestamp}/proposal.pptx
8. Clean up temp dir
```

**Text replacement approach for free text boxes:**
- Read each slide{N}.xml as text
- Case-insensitive regex replace for each placeholder variant
- Write back to file
- Preserve all surrounding XML — NEVER parse and re-serialize the XML tree (corrupts namespaces)

**Logo insertion:**
- Use `python-pptx` just for this step (load the packed PPTX, find slide 5, add picture to defined coordinates)
- Admin should note the pixel coordinates of the logo region in the template — hardcode these as constants in `config.py`

**Expected output:** Given a test input, produces a valid PPTX with all placeholders filled, correct slides included/excluded per tier, N cluster slides for N clusters chosen.

---

### PHASE 5 — Proposal API Endpoint

**Goal:** Single endpoint that runs the full pipeline end-to-end.

**Build:**
- `backend/routes/proposals.py`
- Rate limit check before processing
- Calls LLM service → calls PPT editor → saves cover letter → records in DB

**API endpoint:**
```
POST /proposals/generate
Content-Type: multipart/form-data

Fields:
  company_name: str
  tier: int (1, 2, or 3)
  clusters: list[str] (e.g. ["Music", "Film", "Dance"])
  logo: file (PNG or JPG)
  manager_name: str
  manager_designation: str  ("Media Manager" or "Deputy Media Manager")
  manager_phone: str
  manager_email: str
  custom_notes: str (optional)
  include_csr: bool (Tier 2 optional)
  outreach_city: str (optional, default "Bangalore")

Returns:
  {
    "proposal_id": 42,
    "ppt_download_url": "/proposals/42/download/ppt",
    "cover_letter": "full text here...",
    "portfolio_name": "The Spectacle",
    "output_folder": "outputs/username/TheHindu_20250510_143022/"
  }
```

**Other endpoints:**
- `GET /proposals/` — user's own proposal history
- `GET /proposals/42/download/ppt` — download PPT file
- `GET /proposals/42/cover-letter` — get cover letter text
- `GET /proposals/rate-limit` — check current week usage (returns `{used: 2, limit: 3, resets: "2025-05-12"}`)

**Expected output:** Full generation works end-to-end. Rate limit blocks after 3 attempts. Output files saved and downloadable.

---

### PHASE 6 — Frontend

**Goal:** Simple, clean React UI for users and admin.

**Build:**
- `frontend/` — Vite + React setup
- Pages: Login, Dashboard, Generate Proposal (form), My Outputs, Admin Panel

**Login page:**
- Username + password form
- JWT stored in localStorage

**Dashboard (user):**
- Rate limit status: "2/3 proposals used this week"
- Quick link to generate new proposal
- Recent outputs list

**Generate Proposal form:**
- All form fields as described in Phase 5
- Cluster selection: checkboxes auto-loaded from cluster_descriptions.json
- Logo upload: drag-drop or file picker
- Submit button → shows loading spinner with status messages ("Generating portfolio name... Drafting deliverables... Building PPT...")
- Results panel: PPT download button + cover letter text box (selectable for copy-paste)

**My Outputs page:**
- List of all past proposals (company name, date, tier)
- Download PPT + view cover letter for each

**Admin Panel:**
- User management (create, delete, reset rate limit)
- Resource file management (upload, replace, view list)
- Cluster descriptions editor (text fields per cluster)
- All proposals across all users

**Expected output:** Full working UI. User can go from login → form → download PPT in one flow.

---

### PHASE 7 — Polish & Error Handling

**Goal:** Production-ready reliability.

**Build:**
- Proper error messages (LLM failure, bad file, rate limit, invalid tier)
- Cleanup on failure (delete temp files if pipeline crashes midway)
- Input validation (logo must be image, tier must be 1–3, at least 1 cluster selected)
- Long-running requests: add async background task (FastAPI BackgroundTasks) so the 30–60 second generation doesn't timeout
- Add `/proposals/{id}/status` endpoint so frontend can poll until done
- Loading state in frontend (poll status every 2 seconds, show progress)
- Admin can view error logs for failed generations

**Expected output:** App handles all edge cases gracefully. Generation runs in background. Frontend shows live progress.

---

## Cost Estimate

| Item | Cost |
|------|------|
| Gemini 1.5 Flash API | Free (1500 req/day free tier) |
| Hosting (local) | ₹0 |
| Hosting (Railway free tier) | ₹0 |
| Total | ₹0/month |

Even if usage exceeds free tier: Gemini Flash is $0.075 per 1M input tokens. 30 users × 3 proposals = 90 proposals/week. Each proposal ~5000 tokens input. = 450K tokens/week. Well within free tier. **Cost: ₹0.**

---

## What Is NOT Automated (Stays Manual)

- Finding contacts (phone numbers via extensions, LinkedIn searches)
- Sending the proposal email/WhatsApp
- Follow-up calls and negotiations
- Signing the MOU

---

## Notes for Claude Code

- Never edit the two base files (FMR_PROJECT_PLAN.md, FMR_TECH_SPEC.md)
- Build one phase at a time. Do not start Phase N+1 until Phase N is confirmed working.
- When you need the human to do something (API keys, placing files), STOP, print a clear numbered list of what they need to do, then wait.
- All file paths use forward slashes. Assume Linux/Mac development.
- All LLM calls use `google-generativeai` Python SDK with model `gemini-1.5-flash`.
- SQLite database file lives at `database/fmr.db`.
- NEVER hardcode credentials — always read from `.env` via `python-dotenv`.
