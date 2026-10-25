from app import db, main
from app.config import settings


def _with(value):
    old = settings.extra_users
    object.__setattr__(settings, "extra_users", value)
    return old


def test_extra_users_are_created_and_can_log_in(client):
    old = _with("9901|Dr. Rao|faculty|Faculty-Pass-1; 2303A9902||student|Student-Pass-2 ;bad|x|faculty|short;9903|x|principal|Long-Enough-1;onlytwo|parts")
    try:
        assert main._seed_extra_users() == 2  # the three bad entries are skipped, not fatal
    finally:
        _with(old)
    f = client.post("/api/auth/login", json={"username": "9901", "password": "Faculty-Pass-1", "portal": "faculty"})
    assert f.status_code == 200 and f.json()["user"]["name"] == "Dr. Rao" and f.json()["user"]["must_change_password"] is False
    s = client.post("/api/auth/login", json={"username": "2303a9902", "password": "Student-Pass-2", "portal": "student"})
    assert s.status_code == 200 and s.json()["user"]["name"] == "2303A9902"
    assert db.get_user_by_username("bad") is None and db.get_user_by_username("9903") is None


def test_extra_users_survive_a_wiped_database(client):
    """Simulates Render restarting with an empty disk: running the seeder again brings the accounts back."""
    old = _with("9911||faculty|Faculty-Pass-9")
    try:
        main._seed_extra_users()
        from contextlib import closing
        with closing(db.connect()) as c:
            c.execute("DELETE FROM users WHERE username = '9911'"); c.commit()
        assert db.get_user_by_username("9911") is None
        main._seed_extra_users()
    finally:
        _with(old)
    assert client.post("/api/auth/login", json={"username": "9911", "password": "Faculty-Pass-9"}).status_code == 200
