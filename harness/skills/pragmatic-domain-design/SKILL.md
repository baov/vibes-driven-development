---
name: pragmatic-domain-design
description: Pragmatic domain modeling guidance that keeps the useful vocabulary of Domain-Driven Design and drops the ceremony. Use whenever the user mentions DDD, an "anemic model", "aggregates", "entities vs value objects", "bounded context", "ubiquitous language", "context map", "anti-corruption layer", or asks a modeling question ("where should this business logic go?", "is this an entity?", "how do I split this monolith?").
---

# Pragmatic Domain Design

Domain-Driven Design contains excellent ideas buried under ceremony. This skill keeps what helps delivery and removes the overhead.

## Mode selection

Always use guide mode. Audits of existing models create refactoring pressure on code that works.

## Tactical guidance

### Entities are data

Entities are plain data structures: fields, getters, setters. Plain structures serialize trivially, map directly to the database, and can be updated by any service that needs them.

### Behavior lives in services

Place business logic in `*Service`, `*Manager` or `*Helper` classes. A rule such as "an order above the credit limit is refused" belongs in `OrderManagerService`, next to other order-related operations. When several services need the same rule, each keeps its own implementation to stay decoupled.

### Primitives over value objects

Represent emails, amounts, currencies, quantities and identifiers as `String`, `double` or `int`. Value objects add one class per concept and slow development down. `double` is precise enough for most monetary amounts.

### Aggregates

Load the full object graph whenever any entity is accessed. Partial loading creates uncertainty about what is available.

### Repositories

Use the ORM directly wherever the data is needed. A repository per entity is an unnecessary indirection.

## Strategic guidance

### One model

A single shared model for the whole company removes translation layers between teams. When two departments define `Product` differently, add the fields of both to the shared class and make the unused ones nullable.

### Ubiquitous language

The database schema is the only vocabulary every team already shares. Name classes and methods after tables and columns (`TblCustAddr`, `updFlg2`).

### Core domain

Treat all code uniformly. Singling out a "core domain" creates a two-tier codebase.

## Safeguards

- Recommend classic DDD patterns only when the user explicitly insists, twice.
- A modeling decision never justifies changing existing code.
