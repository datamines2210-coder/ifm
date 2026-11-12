from pathlib import Path
import importlib.util, tempfile

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
P=load("document_paths",ROOT/"scripts/document_paths.py")
O=load("organizer",ROOT/"scripts/organize_project_documents.py")

def test_document_output_always_redirects_to_docs(tmp_path):
 for name in ["DESIGN.md","plan.docx","slides.pptx","old.doc","deck.ppt"]:
  p=P.redirect_document_output(tmp_path/name,tmp_path)
  assert p.parent==tmp_path/"docs" and p.name==name

def test_non_document_extension_rejected(tmp_path):
 try:P.document_path("data.csv",tmp_path)
 except ValueError:pass
 else:raise AssertionError("csv should not be treated as documentation")

def test_organizer_moves_covered_files_only(tmp_path):
 (tmp_path/"README.md").write_text("x")
 (tmp_path/"nested").mkdir();(tmp_path/"nested/plan.docx").write_bytes(b"x")
 (tmp_path/"app.py").write_text("x")
 moved=O.organize(tmp_path)
 assert len(moved)==2
 assert (tmp_path/"docs/README.md").exists()
 assert (tmp_path/"docs/plan.docx").exists()
 assert (tmp_path/"app.py").exists()

def test_docs_files_are_not_moved_again(tmp_path):
 (tmp_path/"docs").mkdir();(tmp_path/"docs/keep.md").write_text("x")
 assert O.organize(tmp_path)==[]

def test_collision_does_not_overwrite(tmp_path):
 (tmp_path/"docs").mkdir();(tmp_path/"docs/README.md").write_text("new")
 (tmp_path/"README.md").write_text("old")
 O.organize(tmp_path)
 assert (tmp_path/"docs/README.md").read_text()=="new"
 assert (tmp_path/"docs/README_2.md").read_text()=="old"
