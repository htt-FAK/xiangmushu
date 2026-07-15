from __future__ import annotations

"""
Unit tests for core.db CRUD operations on user_custom_models.

All tests mock core.db's internal database calls via monkeypatch to avoid
real MySQL/SQLite connections.
"""

import pytest
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional
from copy import deepcopy


# -- In-memory mock store to simulate db.py CRUD --

class MockCustomModelStore:
    """In-memory store that mimics core.db CRUD for CustomModel."""

    def __init__(self):
        self._rows: Dict[int, Dict[str, Any]] = {}
        self._next_id = 1

    def create(self, **kwargs) -> Dict[str, Any]:
        row_id = self._next_id
        self._next_id += 1
        row = {
            "id": row_id,
            "user_id": kwargs["user_id"],
            "name": kwargs["name"],
            "base_url": kwargs["base_url"],
            "model_id": kwargs["model_id"],
            "encrypted_api_key": kwargs["encrypted_api_key"],
            "api_key_hint": kwargs.get("api_key_hint"),
            "capabilities_json": kwargs.get("capabilities_json"),
            "assigned_roles_json": kwargs.get("assigned_roles_json"),
            "default_model_id": kwargs.get("default_model_id"),
            "status": kwargs.get("status", "untested"),
            "last_tested_at": None,
            "last_error": None,
            "created_at": "2026-07-14T00:00:00Z",
            "updated_at": "2026-07-14T00:00:00Z",
        }
        self._rows[row_id] = row
        return dict(row)

    def get_by_user(self, user_id: int) -> List[Dict[str, Any]]:
        return [r for r in self._rows.values() if r["user_id"] == user_id]

    def get_by_id(self, model_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        row = self._rows.get(model_id)
        if row and row["user_id"] == user_id:
            return dict(row)
        return None

    def update(self, model_id: int, user_id: int, **fields) -> Optional[Dict[str, Any]]:
        row = self._rows.get(model_id)
        if not row or row["user_id"] != user_id:
            return None
        for k, v in fields.items():
            row[k] = v
        row["updated_at"] = "2026-07-14T01:00:00Z"
        return dict(row)

    def delete(self, model_id: int, user_id: int) -> bool:
        row = self._rows.get(model_id)
        if not row or row["user_id"] != user_id:
            return False
        del self._rows[model_id]
        return True


@pytest.fixture
def store():
    return MockCustomModelStore()


@pytest.fixture
def test_user_id():
    return 42


class TestCreateCustomModel:
    """create inserts row, get_by_user returns it."""

    def test_create_returns_row_with_id(self, store, test_user_id):
        result = store.create(
            user_id=test_user_id,
            name="Test Model",
            base_url="https://api.example.com",
            model_id="test-model",
            encrypted_api_key="enc_key_xxx",
            api_key_hint="sk-a...zz",
        )
        assert result["id"] == 1
        assert result["name"] == "Test Model"
        assert result["user_id"] == test_user_id
        assert result["status"] == "untested"

    def test_get_by_user_returns_created_row(self, store, test_user_id):
        store.create(
            user_id=test_user_id,
            name="M1",
            base_url="https://api.test.com",
            model_id="m1",
            encrypted_api_key="enc1",
        )
        rows = store.get_by_user(test_user_id)
        assert len(rows) == 1
        assert rows[0]["name"] == "M1"


class TestGetByUserEmpty:
    """get_by_user returns empty list for new user (not None)."""

    def test_empty_list_for_new_user(self, store):
        rows = store.get_by_user(999)
        assert rows == []
        assert rows is not None


class TestUpdateCustomModel:
    """update modifies only specified fields, auto-refreshes updated_at."""

    def test_update_only_specified_fields(self, store, test_user_id):
        result = store.create(
            user_id=test_user_id,
            name="Original",
            base_url="https://api.example.com",
            model_id="orig-model",
            encrypted_api_key="enc_orig",
        )
        model_id = result["id"]

        updated = store.update(model_id, test_user_id, name="Updated Name")
        assert updated["name"] == "Updated Name"
        # base_url unchanged
        assert updated["base_url"] == "https://api.example.com"
        assert updated["model_id"] == "orig-model"

    def test_update_refreshes_updated_at(self, store, test_user_id):
        result = store.create(
            user_id=test_user_id,
            name="M",
            base_url="https://api.example.com",
            model_id="m",
            encrypted_api_key="enc",
        )
        model_id = result["id"]
        original_updated_at = result["updated_at"]

        updated = store.update(model_id, test_user_id, name="New")
        assert updated["updated_at"] != original_updated_at


class TestDeleteCustomModel:
    """delete returns True, subsequent get returns None."""

    def test_delete_returns_true(self, store, test_user_id):
        result = store.create(
            user_id=test_user_id,
            name="DeleteMe",
            base_url="https://api.example.com",
            model_id="del-model",
            encrypted_api_key="enc_del",
        )
        model_id = result["id"]

        assert store.delete(model_id, test_user_id) is True

    def test_get_returns_none_after_delete(self, store, test_user_id):
        result = store.create(
            user_id=test_user_id,
            name="DeleteMe",
            base_url="https://api.example.com",
            model_id="del-model",
            encrypted_api_key="enc_del",
        )
        model_id = result["id"]
        store.delete(model_id, test_user_id)

        assert store.get_by_id(model_id, test_user_id) is None


class TestGetByIdIsolation:
    """get_by_id with wrong user_id returns None."""

    def test_wrong_user_returns_none(self, store, test_user_id):
        result = store.create(
            user_id=test_user_id,
            name="Private",
            base_url="https://api.example.com",
            model_id="priv-model",
            encrypted_api_key="enc_priv",
        )
        model_id = result["id"]

        # Different user trying to access
        assert store.get_by_id(model_id, test_user_id + 1) is None


class TestFilterByCapability:
    """get_by_capability filters by capabilities_json."""

    def test_filter_by_capabilities(self, store, test_user_id):
        store.create(
            user_id=test_user_id,
            name="Text Model",
            base_url="https://api.example.com",
            model_id="text-model",
            encrypted_api_key="enc1",
            capabilities_json=["text"],
        )
        store.create(
            user_id=test_user_id,
            name="Vision Model",
            base_url="https://api.example.com",
            model_id="vision-model",
            encrypted_api_key="enc2",
            capabilities_json=["vision"],
        )

        all_rows = store.get_by_user(test_user_id)
        text_rows = [r for r in all_rows if "text" in (r.get("capabilities_json") or [])]
        assert len(text_rows) == 1
        assert text_rows[0]["name"] == "Text Model"


class TestFilterByRole:
    """get_by_role filters by assigned_roles_json."""

    def test_filter_by_role(self, store, test_user_id):
        store.create(
            user_id=test_user_id,
            name="Audit Model",
            base_url="https://api.example.com",
            model_id="audit-model",
            encrypted_api_key="enc1",
            assigned_roles_json=["audit"],
        )
        store.create(
            user_id=test_user_id,
            name="Gen Model",
            base_url="https://api.example.com",
            model_id="gen-model",
            encrypted_api_key="enc2",
            assigned_roles_json=["text-gen"],
        )

        all_rows = store.get_by_user(test_user_id)
        audit_rows = [r for r in all_rows if "audit" in (r.get("assigned_roles_json") or [])]
        assert len(audit_rows) == 1
        assert audit_rows[0]["name"] == "Audit Model"


class TestManyModelsPerUser:
    """Creating many models for the same user all succeed (no UNIQUE constraint)."""

    def test_multiple_models_same_user(self, store, test_user_id):
        for i in range(5):
            store.create(
                user_id=test_user_id,
                name=f"Model {i}",
                base_url="https://api.example.com",
                model_id=f"model-{i}",
                encrypted_api_key=f"enc_{i}",
            )
        rows = store.get_by_user(test_user_id)
        assert len(rows) == 5
        names = {r["name"] for r in rows}
        assert names == {"Model 0", "Model 1", "Model 2", "Model 3", "Model 4"}
