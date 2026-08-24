---
name: structured-formatter
description: Formats incoming server, hardware, and system metrics for structured reporting.
allowed-tools: 
---
# Structured Formatter

Format and transform system and infrastructure metrics into standardized outputs.

## When to Use

- When parsing and converting server metrics (CPU, memory, disk, network) into reports.
- When generating structured data outputs from raw telemetry strings.

## Output Format

- Output format: Field: value pairs on separate lines.

## Steps

1. Parse the input metric tokens.
2. Format each field as `Field: Value`.
