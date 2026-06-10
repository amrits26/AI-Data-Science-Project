#!/usr/bin/env python
"""Quick local test for fine-tuned Imperial chatbot model loading and inference."""

from __future__ import annotations

import importlib.util
import os
import sys
import types


def _load_chatbot_module():
    """Load imperial_chatbot directly while avoiding heavy agents package side imports."""
    project_root = os.path.abspath(os.path.dirname(__file__))
    backend_dir = os.path.join(project_root, "backend")
    app_dir = os.path.join(backend_dir, "app")
    agents_dir = os.path.join(app_dir, "agents")

    if "backend" not in sys.modules:
        pkg = types.ModuleType("backend")
        pkg.__path__ = [backend_dir]
        sys.modules["backend"] = pkg

    if "backend.app" not in sys.modules:
        pkg = types.ModuleType("backend.app")
        pkg.__path__ = [app_dir]
        sys.modules["backend.app"] = pkg

    if "backend.app.agents" not in sys.modules:
        pkg = types.ModuleType("backend.app.agents")
        pkg.__path__ = [agents_dir]
        sys.modules["backend.app.agents"] = pkg

    module_path = os.path.join(agents_dir, "imperial_chatbot.py")
    spec = importlib.util.spec_from_file_location("backend.app.agents.imperial_chatbot", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load imperial_chatbot module")

    module = importlib.util.module_from_spec(spec)
    sys.modules["backend.app.agents.imperial_chatbot"] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    chatbot = _load_chatbot_module()
    ask_imperial = chatbot.ask_imperial

    question = "What's your best price on a 2022 Toyota Camry?"
    result = ask_imperial(question)

    print("Question:", question)
    print("Source:", result.get("source"))
    print("Type:", result.get("question_type"))
    print("Answer:")
    print(result.get("answer", ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
