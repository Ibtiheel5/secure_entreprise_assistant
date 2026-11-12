"""Seed idempotent : départements, permissions, rôles, utilisateurs fictifs.
Usage : python -m app.database.seed   (SEED_PASSWORD requis, sinon un mot de passe aléatoire est généré et affiché une fois)"""
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.models import Department, Permission, Role, User
from app.permissions.catalog import DEPARTMENTS, PERMISSIONS, ROLES
from app.security.passwords import hash_password

DOMAIN = "nordia-demo.com"  # entreprise et employés 100 % fictifs
USERS = [
    ("admin", "Amine Admin", "IT", ["SYSTEM_ADMIN"]),
    ("ceo", "Camille Durand", "POLICIES", ["CEO"]),
    ("hr.manager", "Hana Ben Salah", "HR", ["HR_MANAGER"]),
    ("hr.employee", "Hedi Trabelsi", "HR", ["HR_EMPLOYEE"]),
    ("it.manager", "Ines Gharbi", "IT", ["IT_MANAGER"]),
    ("it.employee", "Idriss Mansouri", "IT", ["IT_EMPLOYEE"]),
    ("finance.manager", "Farah Jaziri", "FINANCE", ["FINANCE_MANAGER"]),
    ("finance.employee", "Fares Hamdi", "FINANCE", ["FINANCE_EMPLOYEE"]),
    ("employee", "Gabriel Morel", "POLICIES", ["GENERAL_EMPLOYEE"]),
]


def seed(db: Session, password: str) -> None:
    depts = {}
    for code, name in DEPARTMENTS.items():
        d = db.scalar(select(Department).where(Department.code == code)) or Department(code=code, name=name)
        db.add(d)
        depts[code] = d
    perms = {}
    for code, desc in PERMISSIONS.items():
        p = db.scalar(select(Permission).where(Permission.code == code)) or Permission(code=code, description=desc)
        db.add(p)
        perms[code] = p
    roles = {}
    for name, (desc, plist) in ROLES.items():
        r = db.scalar(select(Role).where(Role.name == name)) or Role(name=name)
        r.description = desc
        r.permissions = [perms[c] for c in plist]
        db.add(r)
        roles[name] = r
    db.flush()
    for local, full_name, dept, rnames in USERS:
        email = f"{local}@{DOMAIN}"
        if db.scalar(select(User).where(User.email == email)):
            continue
        db.add(User(email=email, full_name=full_name, hashed_password=hash_password(password),
                    department_id=depts[dept].id, roles=[roles[n] for n in rnames]))
    db.commit()


if __name__ == "__main__":
    from app.database.session import SessionLocal

    pwd = get_settings().seed_password
    if not pwd:
        pwd = secrets.token_urlsafe(14) + "aA1"
        print(f"SEED_PASSWORD not set -> generated one-time password for all demo users: {pwd}")
    with SessionLocal() as session:
        seed(session, pwd)
    print(f"Seeded {len(USERS)} demo users @{DOMAIN}")
