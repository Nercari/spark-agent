---
name: user:codebase-design
description: Shared discipline and vocabulary for designing deep modules with small interfaces, clean seams, and testability. Use when designing interfaces, modules, or boundaries.
---
# Codebase Design

Establish a shared vocabulary and set of design principles for creating deep modules, clear seams, and maintainable software architecture.

## When to Use

- When designing new modules, interfaces, or system boundaries.
- When deciding where to place test seams and how to expose functionality.
- When refactoring shallow modules into deep modules.

## Key Vocabulary and Principles

- **Module**: An interface plus an implementation hiding complexity.
- **Interface**: The formal contract exposed to callers; keep it minimal.
- **Depth**: Deep modules have simple interfaces hiding significant implementation complexity. Shallow modules add indirection without hiding complexity.
- **Seam**: A place where you can alter behavior or test without editing the calling code.
- **Adapter**: Translates between external boundaries and internal domain models.
- **Leverage**: High leverage interfaces provide powerful capabilities through minimal surface area.
- **Locality**: Code that changes together stays together.

## Steps

1. **Identify the Core Domain Concept**: Define the capability being modeled.
2. **Design the Interface First**: Ensure the public surface is minimal, expressive, and testable.
3. **Hide Implementation Details**: Encapsulate internal data structures and auxiliary helpers behind the interface.
4. **Define Test Seams**: Align testing surfaces with the public module interface rather than internal guts.

## Gotchas

- Avoid pass-through or shallow abstractions that simply mirror underlying libraries without adding leverage.
