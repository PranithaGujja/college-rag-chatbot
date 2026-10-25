"""
Create accounts for many students/faculty at once from a CSV of college IDs.

    python scripts/import_users.py users.csv

users.csv (first line is the header; only "id" is required):
    id,name,role
    2303A52481,Asha Rao,student
    2303A51549,,student          <- name and role are optional (role defaults to student)
    EMP1001,Dr. K. Reddy,faculty

Every NEW id gets its own random temporary password and must set a new one at first login.
The temporary passwords are written to  credentials_<date-time>.csv  - hand each person only their own
row, then delete that file. IDs that already exist are skipped (their passwords are NOT touched).
To give someone a new temporary password use:  python scripts/reset_password.py <id>
"""
import csv
import re
import secrets
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db, security  # noqa: E402

ID_RE = re.compile(r"^[A-Za-z0-9._@-]{3,40}$")
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"  # no look-alikes (0/O, 1/l/I)


def temp_password(n: int = 10) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(n))


def import_users(csv_path: str):
    """Returns (created, skipped, errors). `created` rows include the temporary password."""
    db.init_db()
    created, skipped, errors = [], [], []
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [(h or "").strip().lower() for h in (reader.fieldnames or [])]
        if "id" not in reader.fieldnames:
            raise SystemExit('The CSV must have a header line with a column named "id" (for example: id,name,role).')
        for n, row in enumerate(reader, start=2):
            uid = (row.get("id") or "").strip()
            if not uid:
                continue
            role = (row.get("role") or "student").strip().lower()
            name = " ".join((row.get("name") or "").split()) or uid
            if not ID_RE.match(uid):
                errors.append(f"line {n}: '{uid}' is not a valid ID (3-40 letters/numbers, no spaces)")
                continue
            if role not in ("student", "faculty"):
                errors.append(f"line {n}: '{uid}' has role '{role}' (must be student or faculty)")
                continue
            pw = temp_password()
            try:
                db.create_user(uid, name, role, security.hash_password(pw), must_change=True)
            except sqlite3.IntegrityError:
                skipped.append(uid)
                continue
            created.append({"id": uid, "name": name, "role": role, "temporary_password": pw})
    return created, skipped, errors


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    created, skipped, errors = import_users(sys.argv[1])
    if created:
        out = Path(f"credentials_{datetime.now():%Y%m%d_%H%M%S}.csv")
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["id", "name", "role", "temporary_password"])
            w.writeheader()
            w.writerows(created)
        print(f"\nCreated {len(created)} account(s). Temporary passwords saved in: {out.resolve()}")
        print("Give each person only their own row, then DELETE that file.\n")
        for r in created:
            print(f"  {r['id']:<14} {r['role']:<8} {r['temporary_password']}")
    if skipped:
        print(f"\nSkipped {len(skipped)} ID(s) that already exist: {', '.join(skipped)}")
    for e in errors:
        print("ERROR:", e)
    if not (created or skipped or errors):
        print("No rows found in the file.")


if __name__ == "__main__":
    main()
