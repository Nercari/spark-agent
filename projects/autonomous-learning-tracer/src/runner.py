"""Tracer execution runner demonstrating the autonomous learning loop."""

import os
import shutil
import tempfile
from platform.learning.contracts import VerificationStatus, MutationDecision
from platform.learning.evidence_recorder import EvidenceRecorder
from platform.learning.verifier import OutcomeVerifier
from platform.learning.version_store import SkillVersionStore
from platform.learning.reviewer import BackgroundLearningReviewer
from platform.learning.commit_engine import LearningCommitEngine


def run_tracer_cycle(base_dir: str = "/working_dir/c_b490a8c7dd21c813", isolated: bool = True):
    if isolated:
        temp_dir = tempfile.mkdtemp()
        skills_dir = os.path.join(temp_dir, "skills")
        evidence_dir = os.path.join(temp_dir, "evidence")
        audit_log = os.path.join(temp_dir, "audit_log.jsonl")
        src_skill = os.path.join(base_dir, "skills", "structured-formatter")
        dst_skill = os.path.join(skills_dir, "structured-formatter")
        os.makedirs(dst_skill, exist_ok=True)
        shutil.copyfile(os.path.join(src_skill, "SKILL.md"), os.path.join(dst_skill, "SKILL.md"))
    else:
        temp_dir = None
        skills_dir = os.path.join(base_dir, "skills")
        evidence_dir = os.path.join(base_dir, "projects", "autonomous-learning-tracer", "artifacts", "evidence")
        audit_log = os.path.join(base_dir, "projects", "autonomous-learning-tracer", "artifacts", "audit_log.jsonl")

    try:
        version_store = SkillVersionStore(base_skills_dir=skills_dir)
        reviewer = BackgroundLearningReviewer(version_store=version_store)
        commit_engine = LearningCommitEngine(version_store=version_store, audit_log_path=audit_log)

        skill_name = "user:structured-formatter"
        active_skill = version_store.get_active_version(skill_name)
        if not active_skill:
            raise ValueError(f"Skill '{skill_name}' not found under {skills_dir}")

        results = {}

        rec1 = EvidenceRecorder(
            goal="Format server metrics",
            skill_name=skill_name,
            skill_version=active_skill.version_id,
            storage_dir=evidence_dir,
        )
        rec1.record_user_instruction("Format server stats: CPU: 85%, Memory: 60%")
        v1_out = "CPU: 85%\nMemory: 60%"
        rec1.record_user_correction("For this workflow always output JSON with keys 'name' and 'value'.")
        v1_check = OutcomeVerifier.verify_json_format(v1_out, required_keys=["name", "value"])
        rec1.record_verification(v1_check.status, v1_check.reason)
        task1 = rec1.complete_task(v1_out)
        results["task1_verification"] = v1_check.status.value

        mut1 = reviewer.review_task_run(task1)
        results["reviewer_decision"] = mut1.decision.value
        success, msg, v2 = commit_engine.commit_mutation(mut1)
        results["v2_committed"] = success
        results["v2_version_id"] = v2.version_id if v2 else None

        active_v2 = version_store.get_active_version(skill_name)
        rec2 = EvidenceRecorder(
            goal="Format server metrics",
            skill_name=skill_name,
            skill_version=active_v2.version_id,
            storage_dir=evidence_dir,
        )
        rec2.record_user_instruction("Format metrics: Disk: 40%, Net: 100MB")
        v2_out = '[\n  {"name": "Disk", "value": "40%"},\n  {"name": "Net", "value": "100MB"}\n]'
        v2_check = OutcomeVerifier.verify_json_format(v2_out, required_keys=["name", "value"])
        rec2.record_verification(v2_check.status, v2_check.reason)
        task2 = rec2.complete_task(v2_out)
        results["task2_verification"] = v2_check.status.value

        success_v3, _, v3 = version_store.create_new_version(
            skill_name=skill_name,
            base_version_id=v2.version_id,
            base_version_hash=v2.content_hash,
            new_content="CORRUPTED",
            change_reason="Simulated regression",
        )
        v3_check = OutcomeVerifier.verify_json_format("CORRUPTED", required_keys=["name", "value"])
        rb_success, _, restored = commit_engine.rollback_skill(
            skill_name=skill_name,
            target_version_id="v2",
            reason=f"Verification failure on v3: {v3_check.reason}",
        )
        results["rollback_success"] = rb_success
        results["restored_version_id"] = restored.version_id if restored else None

        return results
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
