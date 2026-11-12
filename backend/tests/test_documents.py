import io

from docx import Document as Docx
from reportlab.pdfgen import canvas
from sqlalchemy import func, select

from app.database.models import Document, DocumentChunk
from app.documents.chunking import chunk_text
from app.documents.extract import clean_text


def txt(content: str, name="file.txt"):
    return {"file": (name, content.encode(), "text/plain")}


def up(client, auth, who, title, dept, content, name="file.txt", **extra):
    return client.post("/api/documents/upload", headers=auth(who), files=txt(content, name),
                       data={"title": title, "department_code": dept, **extra})


def test_chunking_respects_size_overlap_and_is_deterministic():
    text = "\n\n".join(f"Paragraph {i}. " + ("word " * 60) for i in range(10))
    a = chunk_text(text, 400, 60)
    assert a == chunk_text(text, 400, 60)
    assert all(len(c) <= 400 + 60 + 4 for c in a) and len(a) > 5
    assert chunk_text("short text", 400, 60) == ["short text"]


def test_clean_text_strips_control_chars():
    assert clean_text("a\x00b\r\n\r\n\r\n\r\nc  d") == "ab\n\nc d"


def test_upload_txt_docx_pdf(client, auth):
    assert up(client, auth, "hr.manager", "Upload TXT", "HR", "Plain text about onboarding procedures.").status_code == 201
    buf = io.BytesIO(); d = Docx(); d.add_paragraph("Docx content about travel expenses."); d.save(buf)
    r = client.post("/api/documents/upload", headers=auth("finance.manager"),
                    files={"file": ("a.docx", buf.getvalue(), "application/octet-stream")},
                    data={"title": "Upload DOCX", "department_code": "FINANCE"})
    assert r.status_code == 201, r.text
    pbuf = io.BytesIO(); c = canvas.Canvas(pbuf); c.drawString(72, 720, "Pdf content about vendor invoices."); c.save()
    r = client.post("/api/documents/upload", headers=auth("finance.manager"),
                    files={"file": ("a.pdf", pbuf.getvalue(), "application/pdf")},
                    data={"title": "Upload PDF", "department_code": "FINANCE"})
    assert r.status_code == 201, r.text


def test_default_acl_is_least_privilege(client, auth):
    r = up(client, auth, "hr.manager", "Least privilege", "HR", "Content about probation periods.").json()
    assert client.get(f"/api/documents/{r['id']}", headers=auth("hr.manager")).status_code == 200
    assert client.get(f"/api/documents/{r['id']}", headers=auth("hr.employee")).status_code == 404


def test_upload_permissions(client, auth):
    assert up(client, auth, "hr.employee", "x1", "HR", "content here").status_code == 403       # pas documents:write
    assert up(client, auth, "hr.manager", "x2", "IT", "content here").status_code == 403         # autre département
    assert up(client, auth, "hr.manager", "x3", "HR", "c", allowed_roles="GOD").status_code == 422
    assert up(client, auth, "hr.manager", "x4", "HR", "content", classification="SECRET").status_code == 422
    assert client.post("/api/documents/upload").status_code == 401


def test_file_validation(client, auth):
    assert up(client, auth, "hr.manager", "bad ext", "HR", "x" * 50, name="evil.exe").status_code == 422
    r = client.post("/api/documents/upload", headers=auth("hr.manager"),
                    files={"file": ("fake.pdf", b"not a pdf at all", "application/pdf")},
                    data={"title": "fake pdf", "department_code": "HR"})
    assert r.status_code == 422
    assert up(client, auth, "hr.manager", "empty", "HR", "", name="e.txt").status_code == 422


def test_new_version_archives_previous_and_search_uses_only_active(client, auth, db):
    d = up(client, auth, "it.manager", "Versioned", "IT", "Backup policy: backups run nightly OLDBACKUPFACT.",
           allowed_roles="IT_MANAGER").json()
    r = client.post(f"/api/documents/{d['id']}/versions", headers=auth("it.manager"),
                    files=txt("Backup policy: backups run hourly NEWBACKUPFACT."), data={"activate": "true"})
    assert r.status_code == 201 and r.json()["current_version"] == 2
    versions = client.get(f"/api/documents/{d['id']}/versions", headers=auth("it.manager")).json()
    assert [(v["version_number"], v["status"]) for v in versions] == [(2, "ACTIVE"), (1, "ARCHIVED")]
    assert set(versions[0]) == {"version_number", "status", "created_at"}  # pas de contenu
    from app.rag.embeddings import get_embedder
    from app.rag.retrieval import search_chunks
    from app.database.models import Role
    rid = {db.scalar(select(Role.id).where(Role.name == "IT_MANAGER"))}
    texts = " ".join(h.content for h in search_chunks(db, rid, get_embedder().embed(["backup policy"])[0], 30))
    assert "NEWBACKUPFACT" in texts and "OLDBACKUPFACT" not in texts


def test_duplicate_version_rejected(client, auth):
    d = up(client, auth, "it.manager", "Dup", "IT", "Same content for duplicate detection.").json()
    r = client.post(f"/api/documents/{d['id']}/versions", headers=auth("it.manager"),
                    files=txt("Same content for duplicate detection."))
    assert r.status_code == 409


def test_draft_version_does_not_replace_active(client, auth):
    d = up(client, auth, "it.manager", "DraftV", "IT", "Active content here for draft test.").json()
    r = client.post(f"/api/documents/{d['id']}/versions", headers=auth("it.manager"),
                    files=txt("Draft replacement content, not approved."), data={"activate": "false"})
    assert r.status_code == 201 and r.json()["current_version"] == 1


def test_lifecycle_delete_purges_chunks_and_is_terminal(client, auth, db):
    d = up(client, auth, "it.manager", "ToDelete", "IT", "Content to be deleted soon, with words.").json()
    assert db.scalar(select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == d["id"])) > 0
    assert client.put(f"/api/documents/{d['id']}/status", json={"status": "DELETED"}, headers=auth("it.manager")).status_code == 403
    assert client.put(f"/api/documents/{d['id']}/status", json={"status": "DELETED"}, headers=auth("admin")).status_code == 200
    db.expire_all()
    assert db.scalar(select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == d["id"])) == 0
    assert client.put(f"/api/documents/{d['id']}/status", json={"status": "ACTIVE"}, headers=auth("admin")).status_code == 409
    assert client.get(f"/api/documents/{d['id']}", headers=auth("it.manager")).status_code == 404


def test_archive_and_restore(client, auth):
    d = up(client, auth, "it.manager", "Arch", "IT", "Archivable content for lifecycle test.").json()
    h = auth("admin")
    assert client.put(f"/api/documents/{d['id']}/status", json={"status": "ARCHIVED"}, headers=h).json()["status"] == "ARCHIVED"
    assert client.get(f"/api/documents/{d['id']}", headers=auth("it.manager")).status_code == 404
    assert client.put(f"/api/documents/{d['id']}/status", json={"status": "ACTIVE"}, headers=h).json()["status"] == "ACTIVE"
    assert client.get(f"/api/documents/{d['id']}", headers=auth("it.manager")).status_code == 200


def test_permissions_update_requires_admin_and_takes_effect(client, auth):
    d = up(client, auth, "hr.manager", "Shareable", "HR", "Shareable content about benefits.").json()
    body = {"allowed_roles": ["HR_MANAGER", "HR_EMPLOYEE"]}
    assert client.put(f"/api/documents/{d['id']}/permissions", json=body, headers=auth("hr.manager")).status_code == 403
    r = client.put(f"/api/documents/{d['id']}/permissions", json=body, headers=auth("admin"))
    assert r.status_code == 200 and r.json()["allowed_roles"] == ["HR_EMPLOYEE", "HR_MANAGER"]
    assert client.get(f"/api/documents/{d['id']}", headers=auth("hr.employee")).status_code == 200
    assert client.put(f"/api/documents/{d['id']}/permissions", json={"allowed_roles": ["NOPE"]}, headers=auth("admin")).status_code == 422


def test_list_is_acl_filtered_and_paginated(client, auth, ids):
    seen = client.get("/api/documents?page_size=100", headers=auth("it.employee")).json()
    titles = {i["title"] for i in seen["items"]}
    assert "sec-IT Security Policy" in titles and "sec-Salary Grid" not in titles
    assert "sec-Old Archived Policy" not in titles and "sec-Draft Policy" not in titles
    assert all(i["allowed_roles"] is None for i in seen["items"])  # l'ACL n'est pas exposée aux utilisateurs
    assert client.get("/api/documents?page_size=1", headers=auth("it.employee")).json()["items"].__len__() == 1
    assert client.get("/api/documents?department=HR&page_size=100", headers=auth("it.employee")).json()["items"] == [
        i for i in seen["items"] if False]  # IT employee ne voit aucun doc HR


def test_admin_stats_use_real_data(client, auth, db):
    s = client.get("/api/admin/stats", headers=auth("admin")).json()
    assert s["total_documents"] == db.scalar(select(func.count(Document.id)))
    assert set(s["documents_by_department"]) == {"HR", "IT", "FINANCE", "POLICIES"}
    assert client.get("/api/admin/stats", headers=auth("ceo")).status_code == 403
