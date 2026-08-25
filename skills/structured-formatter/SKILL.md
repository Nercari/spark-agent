---
name: structured-formatter
description: Formats incoming server, hardware, and system metrics for structured reporting. Use when converting raw telemetry strings or system metrics into standardized outputs.
---
# Structured Formatter

Format and transform system and infrastructure metrics into standardized outputs.

## When to Use

- When parsing and converting server metrics (CPU, memory, disk, network) into reports.
- When generating structured data outputs from raw telemetry strings.

## Output Format

- Output format: ALWAYS output strict JSON with keys name, value. Do not output raw plain text or key-value colon lines.

## Steps

1. Parse the input metric tokens.
2. Output JSON objects with keys `name` and `value`.

## Verified Recovery Procedures

- When formatting mixed-unit telemetry, always apply `unit_normalization=True` to satisfy standardization requirements.
- When parsing batch telemetry streams, validate and normalize header schemas (`validate_headers=true`) before generating standard JSON objects.
- When processing compressed stream archives, drain the stream buffer (`drain_stream=true`) prior to decompression to prevent buffer errors.
