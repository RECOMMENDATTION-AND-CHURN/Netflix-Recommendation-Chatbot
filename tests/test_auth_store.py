"""Unit tests for database/auth_store.py (signup, login, password hashing)."""

from database.auth_store import signup, login, get_all_users, get_user_by_id, update_password


def test_signup_creates_user(isolated_db):
    user_id = signup("alice", "correcthorse")
    assert isinstance(user_id, int)


def test_signup_duplicate_username_returns_none(isolated_db):
    first = signup("bob", "password1")
    second = signup("bob", "differentpassword")
    assert first is not None
    assert second is None


def test_signup_username_is_case_insensitive(isolated_db):
    signup("Carol", "password1")
    # A second signup with different casing of the same username should
    # collide, since login() lowercases before comparing.
    dup = signup("carol", "password2")
    assert dup is None


def test_login_success(isolated_db):
    signup("dave", "mypassword")
    result = login("dave", "mypassword")
    assert result is not None
    assert result["username"] == "dave"


def test_login_wrong_password_fails(isolated_db):
    signup("erin", "correctpassword")
    result = login("erin", "wrongpassword")
    assert result is None


def test_login_nonexistent_user_fails(isolated_db):
    result = login("ghost", "whatever")
    assert result is None


def test_get_all_users_includes_new_signup(isolated_db):
    signup("frank", "password1")
    users = get_all_users()
    usernames = [u["username"] for u in users]
    assert "frank" in usernames


def test_get_user_by_id_roundtrip(isolated_db):
    user_id = signup("grace", "password1")
    fetched = get_user_by_id(user_id)
    assert fetched is not None
    assert fetched["username"] == "grace"


def test_get_user_by_id_missing_returns_none(isolated_db):
    assert get_user_by_id(999999) is None


def test_update_password_success_then_login_with_new_password(isolated_db):
    user_id = signup("heidi", "oldpassword")
    ok = update_password(user_id, "oldpassword", "newpassword123")
    assert ok is True

    assert login("heidi", "oldpassword") is None
    assert login("heidi", "newpassword123") is not None


def test_update_password_wrong_current_password_fails(isolated_db):
    user_id = signup("ivan", "oldpassword")
    ok = update_password(user_id, "totallywrong", "newpassword123")
    assert ok is False
    # Original password should still work — nothing was changed.
    assert login("ivan", "oldpassword") is not None
