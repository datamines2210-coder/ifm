# Project Document Storage Policy

All project documentation and design artifacts must be stored under `docs/`.

Covered extensions:

- `.md`
- `.doc`
- `.docx`
- `.ppt`
- `.pptx`

Run `python scripts/organize_project_documents.py --dry-run` to preview old files that will move, then run `python scripts/organize_project_documents.py` to move them.

New project code that creates a documentation artifact should use `scripts.document_paths.document_path()` or `redirect_document_output()` instead of writing to the current working directory.

`python scripts/check_document_placement.py` is the policy guard and exits non-zero when a covered document exists outside `docs/`.

Existing filename collisions are preserved with `_2`, `_3`, etc.; files are never silently overwritten.
