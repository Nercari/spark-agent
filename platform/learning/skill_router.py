"""Procedural Skill Router & Manifest Parser: Scope-Isolated Skill Routing (EXP-07)."""

import os
import re
import json
import yaml
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Set


@dataclass
class SkillManifest:
    skill_name: str
    display_name: str
    description: str
    triggers: List[str] = field(default_factory=list)
    negative_triggers: List[str] = field(default_factory=list)
    project_scope_id: Optional[str] = None
    active_version_id: str = "v1"
    raw_content: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ProceduralSkillParser:
    """Parses SKILL.md YAML frontmatter, when-to-use sections, and metadata into structured SkillManifest objects."""

    @staticmethod
    def parse_skill_md(content: str, skill_name: str, project_scope_id: Optional[str] = None) -> SkillManifest:
        clean_name = skill_name.split(":", 1)[-1] if ":" in skill_name else skill_name
        display_name = clean_name.replace("-", " ").title()
        description = ""
        triggers = []
        negative_triggers = []

        # 1. Parse YAML frontmatter if present
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    fm = yaml.safe_load(parts[1])
                    if isinstance(fm, dict):
                        description = fm.get("description", "")
                        if "name" in fm:
                            display_name = fm["name"].replace("-", " ").title()
                except Exception:
                    pass

        # 2. Extract 'When to Use' and trigger keywords
        wtu_match = re.search(r"## When to Use\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL | re.IGNORECASE)
        if wtu_match:
            for line in wtu_match.group(1).split("\n"):
                line = line.strip().lstrip("-* ").strip()
                if line:
                    triggers.append(line)

        # 3. Extract Gotchas / Negative boundaries
        gotchas_match = re.search(r"## (?:Gotchas|When NOT to Use)\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL | re.IGNORECASE)
        if gotchas_match:
            for line in gotchas_match.group(1).split("\n"):
                line = line.strip().lstrip("-* ").strip()
                if line:
                    negative_triggers.append(line)

        if not triggers and description:
            triggers.append(description)

        return SkillManifest(
            skill_name=skill_name,
            display_name=display_name,
            description=description,
            triggers=triggers,
            negative_triggers=negative_triggers,
            project_scope_id=project_scope_id,
            raw_content=content,
        )


class ProceduralSkillRouter:
    """Discovers and routes task goals to appropriate versioned procedural skills with scope isolation."""

    def __init__(self, base_skills_dir: Optional[str] = None):
        self.base_skills_dir = base_skills_dir or os.path.expanduser("~/.spark/skills")
        self.manifests: Dict[str, SkillManifest] = {}
        self.load_all_manifests()

    def register_manifest(self, manifest: SkillManifest):
        self.manifests[manifest.skill_name] = manifest

    def load_all_manifests(self):
        if not os.path.exists(self.base_skills_dir):
            return

        for entry in os.listdir(self.base_skills_dir):
            sdir = os.path.join(self.base_skills_dir, entry)
            if not os.path.isdir(sdir):
                continue

            skill_md_path = os.path.join(sdir, "SKILL.md")
            meta_path = os.path.join(sdir, "metadata.json")

            full_skill_name = f"user:{entry}" if not entry.startswith("user:") and not entry.startswith("system:") else entry

            if os.path.exists(skill_md_path):
                with open(skill_md_path, "r", encoding="utf-8") as f:
                    content = f.read()
                manifest = ProceduralSkillParser.parse_skill_md(content, full_skill_name)

                # Overlay metadata.json if present
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, "r", encoding="utf-8") as mf:
                            mdata = json.load(mf)
                            manifest.active_version_id = mdata.get("active_version_id", "v1")
                            manifest.project_scope_id = mdata.get("project_scope_id")
                            if "triggers" in mdata:
                                manifest.triggers = mdata["triggers"]
                            if "negative_triggers" in mdata:
                                manifest.negative_triggers = mdata["negative_triggers"]
                    except Exception:
                        pass

                self.manifests[full_skill_name] = manifest

    def match_skill(
        self,
        task_goal: str,
        project_scope_id: Optional[str] = None,
    ) -> Tuple[Optional[SkillManifest], float, str]:
        """Matches a task goal to the best fitting active procedural skill."""
        best_manifest: Optional[SkillManifest] = None
        best_score = 0.0
        match_reason = "No matching skill found"

        goal_tokens = set(re.findall(r"\w+", task_goal.lower()))

        for name, manifest in self.manifests.items():
            # 1. Scope Isolation Gate: If skill is project-scoped, it cannot match a different project
            if manifest.project_scope_id is not None and manifest.project_scope_id != project_scope_id:
                continue

            # 2. Negative Trigger Rejection Gate
            rejected = False
            for neg in manifest.negative_triggers:
                neg_tokens = set(re.findall(r"\w+", neg.lower()))
                if neg_tokens and neg_tokens.issubset(goal_tokens):
                    rejected = True
                    break
            if rejected:
                continue

            # 3. Trigger & Semantic Scoring
            score = 0.0
            for trig in manifest.triggers:
                trig_tokens = set(re.findall(r"\w+", trig.lower()))
                if not trig_tokens:
                    continue
                overlap = len(goal_tokens & trig_tokens)
                if overlap > 0:
                    sim = overlap / len(trig_tokens)
                    score = max(score, sim)

            # Boost exact name matching
            clean_name = name.split(":", 1)[-1].replace("-", " ")
            if clean_name.lower() in task_goal.lower():
                score = max(score, 0.8)

            # Specialization boost: specific domain skills outrank general meta-routers
            if score >= 0.3:
                if name not in ["user:ask-matt", "system:onboarding"]:
                    score += 0.2

            if score > best_score and score >= 0.4:
                best_score = score
                best_manifest = manifest
                match_reason = f"Matched trigger with confidence {score:.2f}"

        return best_manifest, best_score, match_reason
