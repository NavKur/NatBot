"""Demo data store.

Stands in for the PostgreSQL tables described in `db/schema.sql` (Profiles, Transactions,
Active_Threats, Nudges). State starts from the fake seed data in `data/seed/` and is
persisted to `data/runtime/state.json`, so the voice CLI, the API and the Celery tasks all
see the same data. Swap this class for a SQLAlchemy repository to go to production.
"""

from __future__ import annotations

import copy
import json
import threading
from pathlib import Path
from typing import Any

from nataware.config import settings
from nataware.profile import Profile


class Store:
    def __init__(self, seed_dir: Path, state_path: Path | None = None) -> None:
        self.seed_dir = seed_dir
        self.state_path = state_path
        self._lock = threading.RLock()
        self.state: dict[str, Any] = {}
        self.load()

    # ------------------------------------------------------------------ lifecycle
    def load(self) -> None:
        with self._lock:
            if self.state_path and self.state_path.exists():
                self.state = json.loads(self.state_path.read_text(encoding="utf-8"))
                # Older runtime files may predate newer keys.
                for key, value in self._seed_state().items():
                    self.state.setdefault(key, value)
            else:
                self.state = self._seed_state()

    def save(self) -> None:
        if not self.state_path:
            return
        with self._lock:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.state_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
            tmp.replace(self.state_path)

    def reset(self) -> None:
        """Throw away all runtime changes and go back to the seed data."""
        with self._lock:
            self.state = self._seed_state()
            if self.state_path and self.state_path.exists():
                self.state_path.unlink()

    def _read_seed(self, name: str) -> Any:
        return json.loads((self.seed_dir / name).read_text(encoding="utf-8"))

    def _seed_state(self) -> dict[str, Any]:
        account = self._read_seed("account.json")
        account.pop("_note", None)
        return {
            # The demo profile is pre-loaded so the CLI, tools and tests work out of the box,
            # but the web app treats the user as new until they onboard (or skip).
            "onboarded": False,
            "profile": self._read_seed("demo_profile.json"),
            "account": account,
            "transactions": self._read_seed("transactions.json"),
            "macro_summary": None,
            "active_threats": [],
            "nudges": [],
            "highlights": [],
            "set_asides": [],  # [{"event_id", "weekly", "created_at"}] from "Save £x/week" buttons
            "narration": None,  # cached Claude-written insight text, keyed by a hash of the facts
        }

    # ------------------------------------------------------------------ profile
    def get_profile(self) -> Profile | None:
        raw = self.state.get("profile")
        return Profile.model_validate(raw) if raw else None

    def set_profile(self, profile: Profile) -> None:
        with self._lock:
            self.state["profile"] = profile.model_dump(mode="json")
            self.save()

    # ------------------------------------------------------------------ transactions
    @property
    def transactions(self) -> list[dict[str, Any]]:
        return self.state["transactions"]

    def get_transaction(self, txn_id: str) -> dict[str, Any] | None:
        return next((t for t in self.transactions if t["id"] == txn_id), None)

    def add_transaction(self, txn: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            txn = copy.deepcopy(txn)
            txn["id"] = self._next_txn_id()
            txn.setdefault("tagged", False)
            txn.setdefault("is_flagged", False)
            txn.setdefault("highlight_reason", None)
            self.transactions.append(txn)
            self.transactions.sort(key=lambda t: (t["date"], t.get("time") or "", t["id"]))
            self.save()
            return txn

    def update_transaction(self, txn_id: str, **fields: Any) -> None:
        with self._lock:
            txn = self.get_transaction(txn_id)
            if txn is not None:
                txn.update(fields)

    def _next_txn_id(self) -> str:
        nums = [int(t["id"].split("_")[1]) for t in self.transactions if t["id"].startswith("txn_")]
        return f"txn_{(max(nums) + 1) if nums else 1:04d}"

    # ------------------------------------------------------------------ simple collections
    def get(self, key: str) -> Any:
        return self.state.get(key)

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            self.state[key] = value
            self.save()

    def append(self, key: str, value: Any) -> None:
        with self._lock:
            self.state.setdefault(key, []).append(value)
            self.save()


_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store(settings.seed_dir, settings.runtime_dir / "state.json")
    return _store


def set_store(store: Store | None) -> None:
    """Swap the global store (used by tests)."""
    global _store
    _store = store
