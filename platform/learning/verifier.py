"""Deterministic Outcome Verifier for Task Execution."""

import json
from typing import Any, Dict, List, Optional
from platform.learning.contracts import VerificationResult, VerificationStatus


class OutcomeVerifier:
    """Provides deterministic verification adapters for task outputs."""

    @staticmethod
    def verify_json_format(output: str, required_keys: Optional[List[str]] = None) -> VerificationResult:
        """Verifies that the output is valid JSON and contains required keys."""
        cleaned = output.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except Exception as e:
            return VerificationResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                reason=f"Output is not valid JSON: {str(e)}",
                details={"raw_output": output},
            )

        if required_keys:
            missing_keys = []
            if isinstance(data, dict):
                for k in required_keys:
                    if k not in data:
                        missing_keys.append(k)
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        for k in required_keys:
                            if k not in item and k not in missing_keys:
                                missing_keys.append(k)
                    else:
                        missing_keys.append("(list items are not objects)")
            else:
                missing_keys.append("(root is not object or list)")

            if missing_keys:
                return VerificationResult(
                    status=VerificationStatus.VERIFIED_FAILURE,
                    reason=f"Missing required keys: {', '.join(missing_keys)}",
                    details={"missing_keys": missing_keys, "parsed": data},
                )

        return VerificationResult(
            status=VerificationStatus.VERIFIED_SUCCESS,
            reason="Output matches required JSON schema and keys.",
            details={"parsed": data},
        )

    @staticmethod
    def verify_key_value_format(output: str, required_fields: Optional[List[str]] = None) -> VerificationResult:
        """Verifies that the output contains key-value lines like 'Field: value'."""
        lines = output.strip().splitlines()
        found_fields = {}
        for line in lines:
            if ":" in line:
                k, v = line.split(":", 1)
                found_fields[k.strip()] = v.strip()

        if required_fields:
            missing = [f for f in required_fields if f not in found_fields]
            if missing:
                return VerificationResult(
                    status=VerificationStatus.VERIFIED_FAILURE,
                    reason=f"Missing required key-value fields: {', '.join(missing)}",
                    details={"missing": missing, "found": found_fields},
                )

        if not found_fields:
            return VerificationResult(
                status=VerificationStatus.VERIFIED_FAILURE,
                reason="No key-value pairs detected in output.",
                details={"raw_output": output},
            )

        return VerificationResult(
            status=VerificationStatus.VERIFIED_SUCCESS,
            reason="Output matches key-value format.",
            details={"fields": found_fields},
        )
