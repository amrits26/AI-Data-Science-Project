"""
DealSession manager for conversational paperwork engine.
Stores and manages paperwork sessions for sales chatbot commands.
"""
import threading
import uuid
import json
from pathlib import Path
from typing import Dict, Any, Optional

SESSION_FILE = Path("data/paperwork/deal_sessions.json")
SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)

class DealSession:
    def __init__(self, session_id: str, form_type: str):
        self.session_id = session_id
        self.form_type = form_type  # 'deal_jacket', 'credit_application', 'service_ticket'
        self.vehicle = {}
        self.customer = {}
        self.trade_in = {}
        self.selling_price = None
        self.doc_fee = 250.0
        self.status = "draft"
        self.fields = {}  # Any extra fields needed by paperwork functions

    def to_dict(self):
        return {
            "session_id": self.session_id,
            "form_type": self.form_type,
            "vehicle": self.vehicle,
            "customer": self.customer,
            "trade_in": self.trade_in,
            "selling_price": self.selling_price,
            "doc_fee": self.doc_fee,
            "status": self.status,
            "fields": self.fields,
        }

    @classmethod
    def from_dict(cls, d):
        obj = cls(d["session_id"], d["form_type"])
        obj.vehicle = d.get("vehicle", {})
        obj.customer = d.get("customer", {})
        obj.trade_in = d.get("trade_in", {})
        obj.selling_price = d.get("selling_price")
        obj.doc_fee = d.get("doc_fee", 250.0)
        obj.status = d.get("status", "draft")
        obj.fields = d.get("fields", {})
        return obj


class DealSessionStore:
    def __init__(self):
        self._lock = threading.RLock()
        self._sessions: Dict[str, DealSession] = {}
        self._load()

    def _load(self):
        if SESSION_FILE.exists():
            try:
                with open(SESSION_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for s in data:
                    session = DealSession.from_dict(s)
                    self._sessions[session.session_id] = session
            except Exception:
                pass

    def _save(self):
        with self._lock:
            data = [s.to_dict() for s in self._sessions.values()]
            with open(SESSION_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

    def create_session(self, form_type: str) -> DealSession:
        session_id = str(uuid.uuid4())
        session = DealSession(session_id, form_type)
        with self._lock:
            self._sessions[session_id] = session
            self._save()
        return session

    def get_session(self, session_id: str) -> Optional[DealSession]:
        with self._lock:
            return self._sessions.get(session_id)

    def update_session(self, session_id: str, updates: Dict[str, Any]) -> Optional[DealSession]:
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None
            for k, v in updates.items():
                if hasattr(session, k):
                    setattr(session, k, v)
                else:
                    session.fields[k] = v
            self._save()
            return session

    def delete_session(self, session_id: str) -> bool:
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                self._save()
                return True
            return False

    def all_sessions(self):
        with self._lock:
            return list(self._sessions.values())

# Singleton store
store = DealSessionStore()
