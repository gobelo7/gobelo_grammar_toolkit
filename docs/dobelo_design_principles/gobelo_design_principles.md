# Gobelo Design Principles

## 1. Data-Driven Linguistic Intelligence

**Linguistic intelligence belongs in structured grammar data, not procedural code.**

All language behavior is defined declaratively through structured grammar resources rather than embedded in application logic.

### Includes
- noun class systems
- concords
- TAM markers
- morphophonology
- negation
- derivation rules
- lexical and grammatical variation

### Core implications
- No hardcoded language-specific rules
- Configuration drives behavior
- Runtime mappings derive from grammar definitions
- Grammar data is the system’s primary knowledge source

### Consolidates
- YAML as single source of truth
- Data-driven mapping
- Logic-free data models

---

## 2. Language-Agnostic & Zero-Code Extensibility

**Adding a language should require data, not engineering.**

Gobelo is designed as a language-independent NLP infrastructure where new languages can be introduced without modifying core logic.

### Core implications
- No hardcoded language assumptions
- Generic analyzers and tokenizers
- Plugin-style grammar architecture
- Zero-code language onboarding

### Rule
A new language should require only:

1. a grammar definition
2. registration metadata

…and no core code changes.

### Consolidates
- Language-agnostic architecture
- Zero-code language expansion
- Frugal innovation (partly)

---

## 3. Separation of Concerns & Modular Architecture

**Each component should have one responsibility and minimal knowledge of others.**

Gobelo follows a modular architecture where responsibilities are explicitly separated.

### Examples
- Registry → discovery/resolution
- Loader → parsing and validation
- Models → structured representation
- Engines → computation
- Mappers → transformation/output formatting

### Core implications
- Loose coupling
- Replaceable implementations
- Easier testing
- Safer refactoring
- Clear subsystem boundaries

### Consolidates
- Strict separation of concerns
- Dependency inversion
- Minimal persistent state
- Logic-free data models (partly)

---

## 4. Stable, Explicit, and Safe Interfaces

**Public interfaces should be predictable, typed, and evolution-friendly.**

Consumers interact through stable APIs rather than raw implementation details.

### Core implications
- Typed public contracts
- Immutable value objects
- Explicit semantics for missing data
- Backward compatibility
- Encapsulation of internal schemas

### Rules
- Raw grammar structures never cross public boundaries
- Missing values are explicit
- APIs are treated as long-term contracts

### Consolidates
- Immutable data structures
- Explicit data semantics
- Public API encapsulation
- Stable public contracts
- Convention-guided mutability

---

## 5. Reliability Through Explicit Failure

**Errors should be visible, structured, and diagnosable.**

Gobelo prioritizes correctness and developer clarity through fail-fast behavior and explicit error modeling.

### Core implications
- No silent failures
- No generic exceptions
- Clear distinction between:
  - configuration/data issues
  - programmer defects
- Predictable failure behavior

### Consolidates
- Fail-fast error handling
- Explicit error taxonomy

---

## 6. Frugal, Sustainable Engineering

**Maximize linguistic coverage while minimizing engineering cost.**

Gobelo is intentionally designed for resource-constrained environments and long-term maintainability.

### Core implications
- Reusable generic engines
- Minimal duplication
- Lightweight grammar resources
- Low-cost scaling across languages
- Deferred/lazy resource loading where beneficial

### Consolidates
- Frugal innovation
- Lazy resource validation

---

## 7. Participatory & Linguist-Centered Design

**Language experts should be able to contribute without deep programming knowledge.**

Gobelo is designed for interdisciplinary collaboration among linguists, educators, and NLP developers.

### Core implications
- Human-readable grammar formats
- Accessible documentation
- Separation of linguistic knowledge from software engineering
- Community-driven language growth

### Consolidates
- Linguist-centered documentation
- YAML source of truth (social dimension)

---

## Architectural Philosophy

Gobelo combines several major paradigms:

- Data-driven architecture
- Plugin architecture
- Clean architecture
- Domain-driven design
- Frugal innovation
- Declarative linguistic engineering
- Language-independent NLP infrastructure

### Central Principle

> **Linguistic intelligence belongs in structured grammar data, not procedural code.**

This is the foundational principle tying the architecture together.

### Architectural Flow

**Grammar over code → extensibility → modularity → reliability → sustainability → participation**
