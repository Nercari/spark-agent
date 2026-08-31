from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

try:
    import yaml
except ImportError:
    yaml = None

@dataclass
class SkillManifest:
    name: str
    description: str
    when_to_use: List[str] = field(default_factory=list)
    when_not_to_use: List[str] = field(default_factory=list)
    version: str = "v1"
    raw_content: str = ""
    project_scope: Optional[str] = None

class ProceduralSkillParser:
    """Parses SKILL.md content, extracting YAML frontmatter and operational boundaries."""

    @staticmethod
    def parse_skill_content(content: str, default_name: str = "") -> SkillManifest:
        name = default_name
        description = ""
        when_to_use = []
        when_not_to_use = []

        # Parse YAML frontmatter
        fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        body = content
        if fm_match:
            fm_text = fm_match.group(1)
            body = fm_match.group(2)
            if yaml is not None:
                try:
                    fm_data = yaml.safe_load(fm_text) or {}
                    name = fm_data.get("name", name)
                    description = fm_data.get("description", "")
                except Exception:
                    pass
            else:
                for line in fm_text.splitlines():
                    if line.startswith("name:"):
                        name = line.split(":", 1)[1].strip()
                    elif line.startswith("description:"):
                        description = line.split(":", 1)[1].strip()

        # Parse sections in body
        when_use_match = re.search(r"##\s*When to Use\s*\n(.*?)(?=\n##|$)", body, re.DOTALL | re.IGNORECASE)
        if when_use_match:
            when_to_use = [line.strip("- *").strip() for line in when_use_match.group(1).splitlines() if line.strip("- *").strip()]

        when_not_match = re.search(r"##\s*When NOT to Use\s*\n(.*?)(?=\n##|$)", body, re.DOTALL | re.IGNORECASE)
        if when_not_match:
            when_not_to_use = [line.strip("- *").strip() for line in when_not_match.group(1).splitlines() if line.strip("- *").strip()]

        return SkillManifest(
            name=name,
            description=description,
            when_to_use=when_to_use,
            when_not_to_use=when_not_to_use,
            raw_content=content,
        )

class ProceduralSkillRouter:
    """Routes user queries/goals to matching procedural skills with scope isolation."""

    def __init__(self, manifests: Optional[List[SkillManifest]] = None):
        self.manifests: List[SkillManifest] = manifests or []

    def register_manifest(self, manifest: SkillManifest) -> None:
        self.manifests.append(manifest)

    def match_skill(
        self,
        goal: str,
        project_scope: Optional[str] = None,
    ) -> Optional[SkillManifest]:
        goal_lower = goal.lower()
        goal_tokens = set(re.findall(r"\w+", goal_lower))

        best_score = -1.0
        best_manifest: Optional[SkillManifest] = None

        for m in self.manifests:
            # Enforce project scope isolation if skill manifest has dedicated project_scope
            if m.project_scope is not None and project_scope is not None:
                if m.project_scope != project_scope:
                    continue

            # Check negative triggers first
            negative_triggered = False
            for neg in m.when_not_to_use:
                neg_tokens = set(re.findall(r"\w+", neg.lower()))
                if neg_tokens and neg_tokens.issubset(goal_tokens):
                    negative_triggered = True
                    break
            if negative_triggered:
                continue

            # Calculate match score based on when_to_use and name/description
            score = 0.0
            if m.name.lower() in goal_lower:
                score += 5.0

            for trigger in m.when_to_use:
                trig_tokens = set(re.findall(r"\w+", trigger.lower()))
                overlap = len(goal_tokens.intersection(trig_tokens))
                if overlap > 0:
                    score += overlap * 1.5

            desc_tokens = set(re.findall(r"\w+", m.description.lower()))
            overlap = len(goal_tokens.intersection(desc_tokens))
            score += overlap * 0.5

            if score > best_score and score > 1.0:
                best_score = score
                best_manifest = m

        return best_manifest
