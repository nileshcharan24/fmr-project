"""
Quick Phase 3 test — runs all 5 LLM functions with sample data.
Run from project root: venv\Scripts\python test_llm.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from backend.services.llm import (
    generate_portfolio_name,
    generate_fest_deliverables,
    generate_company_deliverables,
    generate_brand_event_description,
    generate_cover_letter,
)

COMPANY = "Boat Lifestyle"
TIER = 1
CLUSTERS = ["Music", "Dance", "Proshows"]
BANNER_COUNT = 3
POSTS_COUNT = "2 posts and stories"

print("=" * 60)
print(f"Testing all 5 LLM functions for: {COMPANY} (Tier {TIER})")
print("=" * 60)

print("\n[1/5] Portfolio name...")
portfolio = generate_portfolio_name(COMPANY, TIER)
print(f"  >> {portfolio}")

print("\n[2/5] Fest deliverables...")
fest_del = generate_fest_deliverables(COMPANY, TIER, CLUSTERS, BANNER_COUNT, POSTS_COUNT)
print(fest_del)

print("\n[3/5] Company deliverables...")
comp_del = generate_company_deliverables(COMPANY, TIER)
print(comp_del)

print("\n[4/5] Brand event description (Tier 1)...")
brand_desc = generate_brand_event_description(COMPANY)
print(brand_desc)

print("\n[5/5] Cover letter...")
cover = generate_cover_letter(
    company_name=COMPANY,
    tier=TIER,
    portfolio_name=portfolio,
    fest_deliverables=fest_del,
    company_deliverables=comp_del,
    manager_name="Arjun Sharma",
    manager_designation="Media Manager",
)
print(cover)

print("\n" + "=" * 60)
print("All 5 functions completed successfully.")
print("=" * 60)
