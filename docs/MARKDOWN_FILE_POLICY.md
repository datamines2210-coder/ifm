# Markdown file location policy

All project-owned Markdown (`.md`) files must be stored under `docs/`, including hot-patch notes, implementation plans, execution notes, validation reports, and README/change documentation.

The organizer is `scripts/organize_markdown_docs.ps1`. It preserves each Markdown file's previous project-relative path underneath `docs/` and ignores `.venv`, `venv`, `node_modules`, `.git`, and `__pycache__` trees.

The script is safe to rerun. If the destination already contains an identical file, the duplicate source is removed. If the destination contains different content, the script stops instead of overwriting it.

If Windows displays the downloaded-script security warning, review the script and, when trusted, run `Unblock-File .\organize_markdown_docs.ps1` before execution.
