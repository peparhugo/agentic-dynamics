import pytest
from src.models.user import user_store


class TestUserModel:
    def test_create_user(self):
        user = user_store.create("alice", "alice@example.com", "secret123")
        assert user.username == "alice"
        assert user.email == "alice@example.com"
        assert user.role == "user"
        assert user.is_active is True
        assert user.id is not None

    def test_create_admin(self):
        user = user_store.create("bob", "bob@example.com", "secret123", role="admin")
        assert user.role == "admin"

    def test_get_by_id_found(self):
        user = user_store.create("alice", "alice@example.com", "secret123")
        found = user_store.get_by_id(user.id)
        assert found is not None
        assert found.username == "alice"

    def test_get_by_id_not_found(self):
        assert user_store.get_by_id("nonexistent") is None

    def test_get_by_username(self):
        user_store.create("alice", "alice@example.com", "secret123")
        assert user_store.get_by_username("alice") is not None
        assert user_store.get_by_username("nobody") is None

    def test_get_by_email(self):
        user_store.create("alice", "alice@example.com", "secret123")
        assert user_store.get_by_email("alice@example.com") is not None
        assert user_store.get_by_email("nobody@example.com") is None

    def test_list_all(self):
        user_store.create("a", "a@test.com", "pass1")
        user_store.create("b", "b@test.com", "pass2")
        users = user_store.list_all()
        assert len(users) == 2

    def test_update_user(self):
        user = user_store.create("alice", "alice@example.com", "secret123")
        updated = user_store.update(user.id, username="alice2", email="alice2@example.com")
        assert updated is not None
        assert updated.username == "alice2"
        assert updated.email == "alice2@example.com"

    def test_update_password(self):
        user = user_store.create("alice", "alice@example.com", "secret123")
        old_hash = user.password_hash
        user_store.update(user.id, password="newpassword")
        assert user.password_hash != old_hash
        assert user_store.verify_password(user, "newpassword") is True
        assert user_store.verify_password(user, "secret123") is False

    def test_update_nonexistent(self):
        assert user_store.update("nonexistent", username="x") is None

    def test_delete_user(self):
        user = user_store.create("alice", "alice@example.com", "secret123")
        assert user_store.delete(user.id) is True
        assert user_store.get_by_id(user.id) is None
        assert user_store.delete(user.id) is False

    def test_verify_password_correct(self):
        user = user_store.create("alice", "alice@example.com", "secret123")
        assert user_store.verify_password(user, "secret123") is True

    def test_verify_password_wrong(self):
        user = user_store.create("alice", "alice@example.com", "secret123")
        assert user_store.verify_password(user, "wrongpassword") is False

    def test_to_dict_excludes_hash(self):
        user = user_store.create("alice", "alice@example.com", "secret123")
        d = user.to_dict()
        assert "password_hash" not in d
        assert d["username"] == "alice"
        assert d["email"] == "alice@example.com"

    def test_updated_at_changes_on_update(self):
        user = user_store.create("alice", "alice@example.com", "secret123")
        original = user.updated_at
        import time
        time.sleep(0.01)
        user_store.update(user.id, username="alice2")
        assert user.updated_at > original
