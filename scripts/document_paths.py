"""Project document path policy.

All design/documentation artifacts belong under <project>/docs.
Supported document extensions: .md, .doc, .docx, .ppt, .pptx.
"""
from __future__ import annotations
from pathlib import Path

DOCUMENT_EXTENSIONS={".md",".doc",".docx",".ppt",".pptx"}

def project_root() -> Path:
    return Path(__file__).resolve().parents[1]

def docs_root(root: Path|None=None) -> Path:
    root=(root or project_root()).resolve()
    target=root/"docs"
    target.mkdir(parents=True,exist_ok=True)
    return target

def document_path(name: str|Path, root: Path|None=None) -> Path:
    """Return the only permitted project destination for a document artifact."""
    root=(root or project_root()).resolve()
    p=Path(name)
    if p.suffix.lower() not in DOCUMENT_EXTENSIONS:
        raise ValueError(f"Unsupported documentation extension: {p.suffix}")
    # Never honor a caller's current-directory/absolute parent for docs.
    return docs_root(root)/p.name

def redirect_document_output(path: str|Path, root: Path|None=None) -> Path:
    """Redirect a documentation output path to docs/ while preserving its filename."""
    return document_path(Path(path).name,root)
