#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.app.agents.knowledge_base.ingest import ingest_knowledge_base


def main() -> None:
    parser = argparse.ArgumentParser(description="Incrementally ingest files or directories into the FAISS knowledge base")
    parser.add_argument("paths", nargs="*", help="File or directory paths to ingest. Defaults to the configured knowledge_base tree.")
    args = parser.parse_args()

    result = ingest_knowledge_base(paths=args.paths or None)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()