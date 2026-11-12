"""ACL document-level : le filtre SQL (futur retrieval) ne doit renvoyer QUE des documents autorisés."""
import pytest
from sqlalchemy import select

from app.database.models import Department, Document, DocumentStatus, Role, User
from app.permissions.acl import accessible_documents_clause, can_access_document


def _role(db, name):
    return db.scalar(select(Role).where(Role.name == name))


@pytest.fixture()
def docs(db):
    dept = lambda c: db.scalar(select(Department).where(Department.code == c)).id
    rows = {
        "hr_policy": ("HR", DocumentStatus.ACTIVE, ["HR_MANAGER", "HR_EMPLOYEE", "CEO"]),
        "hr_salaries": ("HR", DocumentStatus.ACTIVE, ["HR_MANAGER"]),
        "it_security": ("IT", DocumentStatus.ACTIVE, ["IT_MANAGER", "IT_EMPLOYEE"]),
        "finance_budget": ("FINANCE", DocumentStatus.ACTIVE, ["FINANCE_MANAGER", "CEO"]),
        "general_handbook": ("POLICIES", DocumentStatus.ACTIVE,
                             ["GENERAL_EMPLOYEE", "HR_EMPLOYEE", "IT_EMPLOYEE", "HR_MANAGER", "FINANCE_EMPLOYEE"]),
        "it_archived": ("IT", DocumentStatus.ARCHIVED, ["IT_MANAGER", "IT_EMPLOYEE"]),
        "it_deleted": ("IT", DocumentStatus.DELETED, ["IT_EMPLOYEE"]),
        "it_draft": ("IT", DocumentStatus.DRAFT, ["IT_EMPLOYEE"]),
        "no_acl": ("IT", DocumentStatus.ACTIVE, []),
    }
    out = {}
    for key, (d, status, roles) in rows.items():
        doc = Document(title=f"acltest-{key}", department_id=dept(d), status=status,
                       allowed_roles=[_role(db, r) for r in roles])
        db.add(doc); out[key] = doc
    db.commit()
    yield out
    for d in out.values():
        db.delete(d)
    db.commit()


def visible(db, role_names):
    ids = {_role(db, n).id for n in role_names}
    rows = db.scalars(select(Document).where(Document.title.like("acltest-%"), accessible_documents_clause(ids))).all()
    return {d.title.removeprefix("acltest-") for d in rows}


def test_hr_employee_cannot_see_it_or_salaries(db, docs):
    v = visible(db, ["HR_EMPLOYEE"])
    assert v == {"hr_policy", "general_handbook"}


def test_it_employee_cannot_see_hr_salary_or_inactive(db, docs):
    v = visible(db, ["IT_EMPLOYEE"])
    assert v == {"it_security", "general_handbook"}
    assert not v & {"hr_salaries", "it_archived", "it_deleted", "it_draft"}


def test_hr_manager_not_automatically_granted_finance_or_it(db, docs):
    v = visible(db, ["HR_MANAGER"])
    assert v == {"hr_policy", "hr_salaries", "general_handbook"}


def test_ceo_only_explicitly_authorized(db, docs):
    assert visible(db, ["CEO"]) == {"hr_policy", "finance_budget"}


def test_no_roles_sees_nothing_and_no_acl_means_deny(db, docs):
    assert visible(db, []) == set()
    assert "no_acl" not in visible(db, ["IT_MANAGER", "IT_EMPLOYEE", "CEO", "SYSTEM_ADMIN"])


def test_python_check_matches_sql_filter(db, docs):
    for who in ("HR_EMPLOYEE", "IT_EMPLOYEE", "CEO", "FINANCE_MANAGER", "GENERAL_EMPLOYEE"):
        rid = {_role(db, who).id}
        sql = visible(db, [who])
        py = {k for k, d in docs.items() if can_access_document(rid, d.status, {r.id for r in d.allowed_roles})}
        assert sql == py, who
