"""Procedural Skill Router: Scope-Isolated, Paraphrase-Tolerant Discovery & Trigger Precision (EXP-07)."""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

try:
    import yaml
except ImportError:
    yaml = None

from platform.learning.contracts import SkillVersion
from platform.learning.version_store import SkillVersionStore


@dataclass
class SkillManifest:
    """Indexed L1 representation of a procedural skill."""
    name: str
    description: str
    project_scope: Optional[str] = None
    user_scope: Optional[str] = None
    when_to_use: List[str] = field(default_factory=list)
    when_not_to_use: List[str] = field(default_factory=list)
    keywords: Set[str] = field(default_factory=set)
    is_router: bool = False
    active_version_id: str = "v1"
    content_hash: str = ""


@dataclass
class SkillMatchResult:
    """Result of matching a task goal against indexed procedural skills."""
    skill_name: str
    version_id: str
    confidence_score: float
    matched_triggers: List[str] = field(default_factory=list)
    scope_matched: bool = False
    reason: str = ""


class ProceduralSkillParser:
    """Parses SKILL.md content into an indexed SkillManifest with L1 triggers and boundaries."""

    @staticmethod
    def _tokenize(text: str) -> Set[str]:
        words = re.findall(r'[a-zA-Z0-9_-]{2,}', text.lower())
        stopwords = {
            "the", "and", "for", "with", "that", "this", "from", "into", "when", "use",
            "are", "was", "were", "been", "being", "have", "has", "had", "does", "did",
            "doing", "would", "should", "could", "ought", "how", "what", "which", "who",
            "an", "or", "in", "on", "at", "to", "by", "of", "it", "its", "is", "be",
        }
        return {w for w in words if w not in stopwords}

    @classmethod
    def parse_skill_content(cls, skill_name: str, content: str, version_id: str = "v1", content_hash: str = "") -> SkillManifest:
        """Extracts frontmatter, summary, trigger sections, and negative boundaries from SKILL.md."""
        description = ""
        project_scope = None
        user_scope = None
        when_to_use: List[str] = []
        when_not_to_use: List[str] = []
        summary_text = ""
        is_router = False

        body = content
        # 1. Parse YAML frontmatter if present
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter_raw = parts[1]
                body = parts[2]
                parsed_via_yaml = False
                if yaml is not None:
                    try:
                        meta = yaml.safe_load(frontmatter_raw) or {}
                        description = meta.get("description", "")
                        project_scope = meta.get("project_scope") or meta.get("scope") or meta.get("project")
                        user_scope = meta.get("user_scope") or meta.get("user")
                        if "when_to_use" in meta:
                            raw_wtu = meta["when_to_use"]
                            if isinstance(raw_wtu, list):
                                when_to_use.extend([str(x).strip() for x in raw_wtu])
                            elif isinstance(raw_wtu, str):
                                when_to_use.append(raw_wtu.strip())
                        if "when_not_to_use" in meta or "does_not_apply_when" in meta:
                            raw_wnt = meta.get("when_not_to_use") or meta.get("does_not_apply_when")
                            if isinstance(raw_wnt, list):
                                when_not_to_use.extend([str(x).strip() for x in raw_wnt])
                            elif isinstance(raw_wnt, str):
                                when_not_to_use.append(raw_wnt.strip())
                        parsed_via_yaml = True
                    except Exception:
                        pass

                if not parsed_via_yaml:
                    name_m = re.search(r"^name:\s*(.+)$", frontmatter_raw, re.MULTILINE)
                    desc_m = re.search(r"^description:\s*(.+)$", frontmatter_raw, re.MULTILINE | re.DOTALL)
                    if desc_m:
                        description = desc_m.group(1).strip()

        # 2. Extract summary paragraph right after # Title
        title_match = re.search(r"#\s+[^\n]+\n+([^\n#]+)", body)
        if title_match:
            summary_text = title_match.group(1).strip()

        # 3. Parse Markdown sections for "When to Use" and "When NOT to Use"
        wtu_match = re.search(r"(?:## When to Use|### When to Use)\s*\n(.*?)(?=\n##|\Z)", body, re.DOTALL | re.IGNORECASE)
        if wtu_match:
            lines = [l.strip().lstrip("-*• ").strip() for l in wtu_match.group(1).splitlines() if l.strip().startswith(("-", "*", "•"))]
            for l in lines:
                if l and l not in when_to_use:
                    when_to_use.append(l)

        wnt_match = re.search(r"(?:## When NOT to Use|### When NOT to Use|## Does NOT Apply When)\s*\n(.*?)(?=\n##|\Z)", body, re.DOTALL | re.IGNORECASE)
        if wnt_match:
            lines = [l.strip().lstrip("-*• ").strip() for l in wnt_match.group(1).splitlines() if l.strip().startswith(("-", "*", "•"))]
            for l in lines:
                if l and l not in when_not_to_use:
                    when_not_to_use.append(l)

        # 4. Detect scope constraints in Markdown if not in frontmatter
        if not project_scope:
            scope_match = re.search(r"(?:Scope|Applicable Project|Project Scope):\s*[`'\"]?([a-zA-Z0-9_-]+)[`'\"]?", body, re.IGNORECASE)
            if scope_match:
                project_scope = scope_match.group(1).strip()

        # 5. Router detection (meta-routers vs specific execution procedures)
        lower_desc = description.lower()
        if "router over" in lower_desc or "route engineering" in lower_desc or "meta-skill" in lower_desc:
            is_router = True

        # 6. Extract all keywords
        all_text = f"{skill_name} {description} {summary_text} {' '.join(when_to_use)}"
        keywords = cls._tokenize(all_text)

        return SkillManifest(
            name=skill_name,
            description=description,
            project_scope=project_scope,
            user_scope=user_scope,
            when_to_use=when_to_use,
            when_not_to_use=when_not_to_use,
            keywords=keywords,
            is_router=is_router,
            active_version_id=version_id,
            content_hash=content_hash,
        )


class ProceduralSkillRouter:
    """Indexes procedural skills and provides scope-isolated, paraphrase-tolerant matching."""

    def __init__(self, version_store: SkillVersionStore):
        self.version_store = version_store
        self._manifests: Dict[str, SkillManifest] = {}
        self._indexed = False

    def _ensure_indexed(self):
        if not self._indexed:
            self.refresh_index()

    def refresh_index(self):
        """Indexes all currently active skills in the version store."""
        self._manifests.clear()
        skill_names = self.version_store.list_skills()
        for name in skill_names:
            ver = self.version_store.get_active_version(name)
            if ver and ver.content:
                manifest = ProceduralSkillParser.parse_skill_content(
                    skill_name=name,
                    content=ver.content,
                    version_id=ver.version_id,
                    content_hash=ver.content_hash,
                )
                self._manifests[name] = manifest
        self._indexed = True

    def register_skill_manifest(self, manifest: SkillManifest):
        """Explicitly registers or updates an indexed manifest."""
        self._ensure_indexed()
        self._manifests[manifest.name] = manifest

    def get_manifest(self, skill_name: str) -> Optional[SkillManifest]:
        self._ensure_indexed()
        return self._manifests.get(skill_name)

    def _score_candidate(
        self,
        manifest: SkillManifest,
        goal: str,
        project_scope_id: Optional[str],
        user_scope_id: Optional[str],
    ) -> Tuple[float, List[str], bool, str]:
        """Calculates match score, checks negative boundaries, and enforces scope isolation."""
        goal_tokens = ProceduralSkillParser._tokenize(goal)
        if not goal_tokens:
            return 0.0, [], False, "Empty goal tokens"

        # Gate 1: Strict Scope Isolation
        # If a skill specifies a required project scope, it MUST match the active project scope.
        if manifest.project_scope:
            if not project_scope_id or manifest.project_scope != project_scope_id:
                return 0.0, [], False, f"Disqualified: skill requires project_scope '{manifest.project_scope}', but active scope is '{project_scope_id}'"

        scope_matched = bool(manifest.project_scope and project_scope_id and manifest.project_scope == project_scope_id)

        # Gate 2: Negative Trigger Boundaries (\"When NOT to Use\")
        goal_lower = goal.lower()
        for neg_trigger in manifest.when_not_to_use:
            neg_tokens = ProceduralSkillParser._tokenize(neg_trigger)
            overlap = goal_tokens.intersection(neg_tokens)
            if len(overlap) >= 2 or (len(neg_tokens) == 1 and len(overlap) == 1 and list(overlap)[0] in goal_lower):
                return 0.0, [], False, f"Disqualified by negative trigger boundary: '{neg_trigger}'"

        # Gate 3: Semantic Overlap & Paraphrase Matching
        matched_triggers: List[str] = []
        token_overlap = goal_tokens.intersection(manifest.keywords)
        if not token_overlap:
            return 0.0, [], False, "No keyword overlap"

        # Jaccard base score over goal tokens
        jaccard = len(token_overlap) / len(goal_tokens.union(manifest.keywords))
        goal_coverage = len(token_overlap) / len(goal_tokens)
        score = 0.40 * goal_coverage + 0.30 * jaccard

        # Trigger phrase bonus
        for trigger in manifest.when_to_use:
            trig_tokens = ProceduralSkillParser._tokenize(trigger)
            trig_overlap = goal_tokens.intersection(trig_tokens)
            if trig_overlap:
                trig_ratio = len(trig_overlap) / max(1, len(trig_tokens))
                if trig_ratio >= 0.25:
                    matched_triggers.append(trigger)
                    score += 0.25 * trig_ratio

        # Exact skill name mentioned bonus with strict word boundary
        clean_name = manifest.name.split(":", 1)[-1].replace("-", " ")
        if re.search(rf"\b{re.escape(clean_name)}\b", goal_lower) or re.search(rf"\b{re.escape(manifest.name.lower())}\b", goal_lower):
            score += 0.35
            matched_triggers.append(f"exact_name_match:{manifest.name}")

        # Scope Affinity Bonus
        if scope_matched:
            score += 0.25

        # Specificity vs Meta-Router Penalty
        if manifest.is_router:
            score -= 0.15
        else:
            score += 0.10

        score = min(1.0, max(0.0, score))
        return score, matched_triggers, scope_matched, "Scored candidate"

    def match_skill(
        self,
        goal: str,
        project_scope_id: Optional[str] = None,
        user_scope_id: Optional[str] = None,
        min_confidence: float = 0.30,
    ) -> Optional[SkillMatchResult]:
        """Discovers and selects the single most applicable procedural skill for a task goal."""
        ranked = self.rank_competing_skills(
            goal=goal,
            project_scope_id=project_scope_id,
            user_scope_id=user_scope_id,
            min_confidence=min_confidence,
        )
        return ranked[0] if ranked else None

    def rank_competing_skills(
        self,
        goal: str,
        project_scope_id: Optional[str] = None,
        user_scope_id: Optional[str] = None,
        min_confidence: float = 0.30,
    ) -> List[SkillMatchResult]:
        """Ranks all matching procedural skills by specificity, scope affinity, and semantic relevance."""
        self._ensure_indexed()
        results: List[SkillMatchResult] = []

        for name, manifest in self._manifests.items():
            score, matched_trigs, scope_match, reason = self._score_candidate(
                manifest=manifest,
                goal=goal,
                project_scope_id=project_scope_id,
                user_scope_id=user_scope_id,
            )
            if score >= min_confidence:
                results.append(
                    SkillMatchResult(
                        skill_name=manifest.name,
                        version_id=manifest.active_version_id,
                        confidence_score=round(score, 4),
                        matched_triggers=matched_trigs,
                        scope_matched=scope_match,
                        reason=reason,
                    )
                )

        # Sort descending by (confidence_score, scope_matched, is_not_router)
        results.sort(
            key=lambda r: (
                r.confidence_score,
                r.scope_matched,
                not self._manifests[r.skill_name].is_router,
            ),
            reverse=True,
        )

        return results
