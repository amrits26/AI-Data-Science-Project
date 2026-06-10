from __future__ import annotations

import json

from backend.app.agents.knowledge_base.ingest import ingest_knowledge_base


if __name__ == "__main__":
    result = ingest_knowledge_base()
    print(json.dumps(result, indent=2))
