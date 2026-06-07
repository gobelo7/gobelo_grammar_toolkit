# Gobelo Design Principles — Technical Architecture Guide

## Purpose

This document defines the architectural principles governing Gobelo system design, implementation decisions, extension mechanisms, and contributor expectations.

---

## 1. Data-Driven Linguistic Intelligence

### Principle
**Linguistic intelligence belongs in structured grammar data, not procedural code.**

### Design Rule
Core application logic must remain language-independent.

### Requirements
- No hardcoded language names
- No hardcoded concord systems
- No embedded noun class logic
- No embedded TAM systems
- No embedded morphophonological rules

### Implementation Pattern
All linguistic behavior is externalized into structured grammar definitions.

### Approved Sources
- YAML grammar files
- registry metadata
- lexical resources

---

## 2. Language-Agnostic & Zero-Code Extensibility

### Principle
**Adding a language should require data, not engineering.**

### Design Rule
Adding a new language must not require modification of core system logic.

### Minimum Requirements
1. Grammar definition file
2. Registry entry

### Anti-patterns
❌ if language == "x" logic  
❌ hardcoded linguistic exceptions  
❌ language-specific processing branches

---

## 3. Separation of Concerns & Modular Architecture

### Principle
**Components should maintain narrowly scoped responsibilities.**

### Architectural Boundaries

| Component | Responsibility |
|-----------|----------------|
| Registry | Resource discovery |
| Loader | Parsing + validation |
| Models | Data representation |
| Engines | Linguistic computation |
| Mapper | Output transformation |

### Design Rule
No component should directly depend on unnecessary implementation details.

---

## 4. Stable, Explicit & Safe Interfaces

### Principle
**Public APIs are long-term contracts.**

### Requirements
- Typed dataclasses
- Immutable public objects
- Explicit optionality
- Encapsulation of internal schemas

### Rules
- Raw YAML must never cross API boundaries
- Breaking API changes require major versioning

---

## 5. Reliability Through Explicit Failure

### Principle
**Errors must be structured and diagnosable.**

### Requirements
- No bare exceptions
- No silent failures
- Dedicated exception hierarchy

### Error Categories
- configuration failures
- grammar validation failures
- runtime software defects

---

## 6. Frugal & Sustainable Engineering

### Principle
**Maximize linguistic coverage while minimizing engineering overhead.**

### Optimization Goals
- Generic reusable engines
- Low duplication
- Lightweight resources
- Efficient loading strategies

---

## 7. Participatory & Linguist-Centered Design

### Principle
**Domain experts must be able to contribute directly.**

### Requirements
- Human-readable grammar definitions
- Accessible documentation
- Clear contributor workflows
- Separation of linguistic expertise from software engineering complexity

---

## Core Architectural Sequence

> **Grammar over code → extensibility → modularity → reliability → sustainability → participation**

This sequence defines Gobelo’s architectural philosophy and decision-making framework.
