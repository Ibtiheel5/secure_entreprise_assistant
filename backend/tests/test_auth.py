import time

import jwt
from sqlalchemy import select

from app.database.models import AccessLog, User
from app.security.passwords import hash_password, verify_password
from tests.conftest import DOMAIN, PASSWORD, login

SECRET = "test-secret-key-that-is-long-enough-1234567890"


def test_login_success_returns_token_without_secrets(client):
    r = login(client, "hr.manager")
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer" and body["access_token"]
    assert "password" not in r.text.lower()


def test_login_wrong_password_and_unknown_user_same_error(client):
    a = login(client, "hr.manager", "Wrong-Passw0rd-123")
    b = client.post("/api/auth/login", json={"email": f"nobody@{DOMAIN}", "password": "Whatever-Passw0rd1"})
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


def test_failed_login_is_audited(client, db):
    login(client, "it.employee", "Wrong-Passw0rd-123")
    row = db.scalars(select(AccessLog).where(AccessLog.action == "auth.login", AccessLog.allowed.is_(False))).first()
    assert row is not None and row.user_id is not None


def test_password_is_hashed_with_argon2(db):
    u = db.scalar(select(User).where(User.email == f"ceo@{DOMAIN}"))
    assert u.hashed_password.startswith("$argon2") and PASSWORD not in u.hashed_password
    assert verify_password(PASSWORD, u.hashed_password)
    assert not verify_password("nope", u.hashed_password)


def test_me_requires_auth(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_returns_server_side_identity(client, auth):
    r = client.get("/api/auth/me", headers=auth("hr.manager"))
    assert r.status_code == 200
    d = r.json()
    assert d["email"] == f"hr.manager@{DOMAIN}"
    assert d["department"] == "HR" and d["roles"] == ["HR_MANAGER"]


def test_frontend_supplied_role_or_department_is_ignored(client, auth):
    h = {**auth("employee"), "X-Role": "SYSTEM_ADMIN", "X-Department": "FINANCE", "X-User-Id": "1"}
    d = client.get("/api/users/me", headers=h).json()
    assert d["roles"] == ["GENERAL_EMPLOYEE"] and d["department"] == "POLICIES"
    assert client.get("/api/users", headers=h).status_code == 403
    assert client.get("/api/users?role=SYSTEM_ADMIN", headers=auth("employee")).status_code == 403


def test_tampered_token_rejected(client, auth):
    token = auth("employee")["Authorization"].split()[1]
    bad = token[:-3] + ("AAA" if not token.endswith("AAA") else "BBB")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {bad}"}).status_code == 401


def test_token_signed_with_other_secret_rejected(client):
    forged = jwt.encode({"sub": "1", "jti": "x", "exp": int(time.time()) + 600}, "another-secret-another-secret-123456", "HS256")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_alg_none_token_rejected(client):
    forged = jwt.encode({"sub": "1", "jti": "x", "exp": int(time.time()) + 600}, None, algorithm="none")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_expired_token_rejected(client):
    t = jwt.encode({"sub": "1", "jti": "x", "exp": int(time.time()) - 10}, SECRET, "HS256")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {t}"}).status_code == 401


def test_token_without_jti_rejected(client):
    t = jwt.encode({"sub": "1", "exp": int(time.time()) + 600}, SECRET, "HS256")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {t}"}).status_code == 401


def test_logout_revokes_token(client):
    token = login(client, "finance.employee").json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/auth/me", headers=h).status_code == 200
    assert client.post("/api/auth/logout", headers=h).status_code == 204
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_inactive_user_cannot_use_existing_token(client, db):
    from app.database.models import Department, Role
    u = User(email=f"temp@{DOMAIN}", full_name="Temp User", hashed_password=hash_password(PASSWORD),
             department_id=db.scalar(select(Department.id)), roles=[db.scalar(select(Role).where(Role.name == "GENERAL_EMPLOYEE"))])
    db.add(u); db.commit()
    token = login(client, "temp").json()["access_token"]
    u.is_active = False; db.commit()
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert login(client, "temp").status_code == 401
