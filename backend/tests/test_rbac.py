from app.permissions.catalog import ROLES
from tests.conftest import DOMAIN


def test_all_eight_required_roles_exist_plus_admin():
    required = {"CEO", "HR_MANAGER", "HR_EMPLOYEE", "IT_MANAGER", "IT_EMPLOYEE",
                "FINANCE_MANAGER", "FINANCE_EMPLOYEE", "GENERAL_EMPLOYEE"}
    assert required <= set(ROLES)


def test_non_admin_cannot_create_user_and_denial_is_audited(client, auth, db):
    from sqlalchemy import select
    from app.database.models import AccessLog
    body = {"email": f"x@{DOMAIN}", "full_name": "X Person", "password": "Str0ng-Passw0rd!",
            "department_code": "HR", "roles": ["HR_MANAGER"]}
    for who in ("hr.manager", "ceo", "employee", "it.manager"):
        assert client.post("/api/users", json=body, headers=auth(who)).status_code == 403
    denied = db.scalars(select(AccessLog).where(AccessLog.action == "permission:users:manage",
                                                AccessLog.allowed.is_(False))).all()
    assert len(denied) >= 4


def test_unauthenticated_cannot_create_user(client):
    assert client.post("/api/users", json={}).status_code == 401


def test_admin_creates_user_who_can_login(client, auth):
    body = {"email": f"new.hr@{DOMAIN}", "full_name": "New Hire", "password": "Str0ng-Passw0rd!",
            "department_code": "HR", "roles": ["HR_EMPLOYEE"]}
    r = client.post("/api/users", json=body, headers=auth("admin"))
    assert r.status_code == 201 and r.json()["roles"] == ["HR_EMPLOYEE"]
    assert "password" not in r.text.lower()
    assert client.post("/api/auth/login", json={"email": body["email"], "password": body["password"]}).status_code == 200
    assert client.post("/api/users", json=body, headers=auth("admin")).status_code == 409


def test_admin_user_creation_validation(client, auth):
    base = {"email": f"v@{DOMAIN}", "full_name": "V Person", "password": "Str0ng-Passw0rd!",
            "department_code": "HR", "roles": ["HR_EMPLOYEE"]}
    assert client.post("/api/users", json={**base, "password": "weak"}, headers=auth("admin")).status_code == 422
    assert client.post("/api/users", json={**base, "roles": ["GOD_MODE"]}, headers=auth("admin")).status_code == 422
    assert client.post("/api/users", json={**base, "department_code": "NOPE"}, headers=auth("admin")).status_code == 422
    assert client.post("/api/users", json={**base, "email": "not-an-email"}, headers=auth("admin")).status_code == 422


def test_list_users_pagination_and_permission(client, auth):
    r = client.get("/api/users?page=1&page_size=3", headers=auth("admin")).json()
    assert len(r["items"]) == 3 and r["total"] >= 9 and r["page_size"] == 3
    assert client.get("/api/users?page_size=1000", headers=auth("admin")).status_code == 422
    assert client.get("/api/users", headers=auth("ceo")).status_code == 200
    assert client.get("/api/users", headers=auth("hr.manager")).status_code == 403
    assert "hashed_password" not in client.get("/api/users", headers=auth("admin")).text


def test_effective_permissions_per_role(client, auth):
    hr = client.get("/api/auth/me", headers=auth("hr.employee")).json()["permissions"]
    assert "chat:use" in hr and "users:manage" not in hr and "security:view" not in hr
    ceo = client.get("/api/auth/me", headers=auth("ceo")).json()["permissions"]
    assert "security:view" in ceo and "users:manage" not in ceo


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/health/db").json() == {"status": "ok"}
