import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (one level above backend/)
load_dotenv(Path(__file__).parent.parent / ".env")

# --- Credentials ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
JWT_SECRET = os.getenv("JWT_SECRET", "changeme")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
COHEAD_USERNAME = os.getenv("COHEAD_USERNAME", "")
COHEAD_PASSWORD = os.getenv("COHEAD_PASSWORD", "")

# --- Paths ---
# Persistent data lives under /app/data (Railway volume mount).
# Everything else (resources, temp) stays relative to the project root.
PROJECT_ROOT  = Path(__file__).parent.parent
DATA_DIR      = Path(os.getenv("DATA_DIR", "/app/data"))
RESOURCES_DIR = PROJECT_ROOT / "resources"
OUTPUTS_DIR   = DATA_DIR / "outputs"
TEMP_DIR      = DATA_DIR / "temp"
# DATABASE_PATH env var lets Railway override directly if needed
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(DATA_DIR / "database" / "fmr.db")))
TEMPLATE_PPTX = PROJECT_ROOT / "resources" / "templates" / "sponsorship_proposal.pptx"
COVER_LETTER_TEMPLATE = PROJECT_ROOT / "resources" / "templates" / "cover_letter_template.docx"

# --- Tier rules ---
TIER_CLUSTERS = {1: (3, 5), 2: (2, 3), 3: (1, 1)}   # (min, max) clusters
TIER_BANNERS  = {1: (3, 4), 2: (2, 2), 3: (1, 1)}    # (min, max) banners per cluster
TIER_POSTS    = {
    1: "2 posts + stories",
    2: "1-2 posts + story",
    3: "1 post + story",
}

# --- Slide rules ---
# After python-pptx loads the template and saves, rels are renumbered to
# match filename order (slide1.xml = pos 1, slide2.xml = pos 2, ...).
# These 1-based positions are in that post-save numeric order:
#   10 = Pronite Partnership    (Tier 1 only)
#   13 = Brand event slide      (Tier 1 only)
#   14 = Outreach slide         (Tier 1 only)
#   15 = CSR slide              (Tier 1+2 only)
#   12 = Cluster slide          (duplicated per cluster)
#    5 = Association slide      (logo placement)
SLIDES_TIER_1_ONLY = [10, 13, 14]  # Delete for Tier 2 and 3
SLIDES_TIER_1_2    = [15]           # Delete for Tier 3; optional for Tier 2
CLUSTER_SLIDE_INDEX = 12            # 1-based slide number after template load+save
LOGO_SLIDE_INDEX    = 5             # Association slide (pos 5)

# Logo placement on Slide 5 (Association slide) — right-side box.
# Slide canvas is 20.00" x 11.25". The right box sits at L=14.13", T=4.07",
# W=4.17", H=4.00". We inset the logo slightly inside the box.
LOGO_LEFT_INCHES  = 14.4
LOGO_TOP_INCHES   = 4.5
LOGO_WIDTH_INCHES = 3.6

# --- Outreach defaults ---
OUTREACH_EVENT  = ["Gigahertz", "Festember Football League", "Rolling Reels Film Festival"]
OUTREACH_CITIES = ["Bangalore", "Chennai", "Pondicherry", "Kochi", "Hyderabad"]

# --- Rate limit ---
WEEKLY_LIMIT = 3

# --- LLM ---
GEMINI_MODEL = "gemini-2.5-flash"

# --- JWT ---
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 12  # 12 hours

# --- Frontend URL (for CORS) ---
# Use `or` so an empty-string env var still falls back to the dev default
FRONTEND_URL = os.getenv("FRONTEND_URL") or "http://localhost:5173"

# --- Google OAuth ---
GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI  = os.getenv("GOOGLE_REDIRECT_URI") or "http://localhost:8000/auth/google/callback"
