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
