import json
from pathlib import Path

from docx import Document

from backend.config import RESOURCES_DIR


def read_docx(relative_path: str) -> str:
    """Read a .docx file and return its full text content."""
    full_path = RESOURCES_DIR / relative_path
    if not full_path.exists():
        raise FileNotFoundError(f"Resource file not found: {relative_path}")
    doc = Document(str(full_path))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def read_cluster_descriptions() -> dict:
    """Return the cluster_descriptions.json as a dict."""
    path = RESOURCES_DIR / "clusters" / "cluster_descriptions.json"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_cluster_descriptions(data: dict) -> None:
    """Overwrite cluster_descriptions.json with the given dict."""
    path = RESOURCES_DIR / "clusters" / "cluster_descriptions.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def list_resources() -> list[dict]:
    """Return metadata for all resource files (excluding clusters JSON)."""
    results = []
    skip = {RESOURCES_DIR / "clusters" / "cluster_descriptions.json"}

    for f in sorted(RESOURCES_DIR.rglob("*")):
        if not f.is_file():
            continue
        if f in skip:
            continue
        rel = f.relative_to(RESOURCES_DIR)
        results.append({
            "filename": f.name,
            "path": str(rel).replace("\\", "/"),
            "type": f.suffix.lstrip(".").upper(),
            "size_kb": round(f.stat().st_size / 1024, 1),
            "modified": f.stat().st_mtime,
        })
    return results
