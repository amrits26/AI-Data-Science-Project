import os
import importlib.util
import pkgutil
from pathlib import Path
from sentence_transformers import SentenceTransformer
import numpy as np

SKILLS_DIR = Path(__file__).parent
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

class SkillManager:
    def __init__(self):
        self.skills = []
        self.menu = ""
        self._load_skills()
        self._build_menu()
        self._embedder = SentenceTransformer(EMBEDDING_MODEL)
        self._embed_skill_descriptions()

    def _load_skills(self):
        for finder, name, ispkg in pkgutil.iter_modules([str(SKILLS_DIR)]):
            if name == "__init__":
                continue
            module_path = SKILLS_DIR / f"{name}.py"
            spec = importlib.util.spec_from_file_location(name, module_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self.skills.append({
                "name": getattr(mod, "SKILL_NAME"),
                "description": getattr(mod, "SKILL_DESCRIPTION"),
                "priority": getattr(mod, "SKILL_PRIORITY"),
                "triggers": getattr(mod, "SKILL_TRIGGERS"),
                "embedding": None,  # populated below
                "execute": getattr(mod, "execute"),
                "module": mod
            })
        self.skills.sort(key=lambda s: -s["priority"])

    def _build_menu(self):
        self.menu = "Available skills: " + ", ".join(
            f"{s['name']} ({s['description']})" for s in self.skills
        )
        # Truncate to ~200 tokens if needed
        if len(self.menu.split()) > 150:
            self.menu = self.menu[:1200] + "..."

    def _embed_skill_descriptions(self):
        descriptions = [s["description"] for s in self.skills]
        embeddings = self._embedder.encode(descriptions, normalize_embeddings=True)
        for i, s in enumerate(self.skills):
            s["embedding"] = embeddings[i]
            s["module"].SKILL_EMBEDDING = embeddings[i]

    def resolve(self, query: str):
        q = query.lower()
        # Stage 1: Priority keyword matching
        for skill in self.skills:
            if any(trigger in q for trigger in skill["triggers"]):
                return skill["execute"]
        # Stage 2: Semantic fallback
        q_emb = self._embedder.encode([query], normalize_embeddings=True)[0]
        sims = [float(np.dot(q_emb, s["embedding"])) for s in self.skills]
        max_sim = max(sims)
        if max_sim >= 0.6:
            idx = sims.index(max_sim)
            # Log semantic match
            log_path = Path("data/logs/semantic_triggers.log")
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"{query}\t{sims[idx]:.3f}\t{self.skills[idx]['name']}\n")
            return self.skills[idx]["execute"]
        # Stage 3: Fallback
        for skill in self.skills:
            if skill["name"] == "general_knowledge":
                return skill["execute"]
        # Should never happen
        return lambda q, c, s: {"answer": "No skill matched.", "question_type": "error", "data": {}, "source": "none"}
