"""Give a user a new temporary password (for example when they forgot theirs).
    python scripts/reset_password.py 2303A52481
They must choose a new password at their next login. All their old sessions are signed out."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db, security  # noqa: E402
from scripts.import_users import temp_password  # noqa: E402

if len(sys.argv) != 2:
    sys.exit(__doc__)
db.init_db()
user = db.get_user_by_username(sys.argv[1].strip())
if user is None:
    sys.exit(f"No user with ID '{sys.argv[1]}'.")
pw = temp_password()
db.set_password(user["id"], security.hash_password(pw), must_change=True)
print(f"New temporary password for {user['username']} ({user['role']}): {pw}")
