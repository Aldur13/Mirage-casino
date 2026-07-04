"""Promote an existing registered user to the 'admin' role.

Usage (from the backend/ directory, with the venv active):

    python make_admin.py user@example.com

The user must already be registered. Same shared User node as Mirage Bank
(see backend/make_admin.py there) — role='admin' set here is visible to
both apps. Combine with OWNER_EMAIL (config.py / dependencies.py) once the
casino has its own privileged admin routes, mirroring mirage-bank's
single-super-owner pattern.
"""
import sys

from database import close_driver, get_session


def make_admin(email: str) -> None:
    email = email.strip().lower()
    with get_session() as session:
        result = session.run(
            """
            MATCH (u:User {email: $email})
            SET u.role = 'admin'
            RETURN u.id AS id, u.name AS name, u.email AS email, u.role AS role
            """,
            email=email,
        ).single()

    if result is None:
        print(f"[ERROR] No user found with email '{email}'. Register them first.")
        sys.exit(1)

    print(f"[OK] {result['name']} <{result['email']}> is now an administrator "
          f"(role={result['role']}).")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python make_admin.py <email>")
        sys.exit(2)
    try:
        make_admin(sys.argv[1])
    finally:
        close_driver()
