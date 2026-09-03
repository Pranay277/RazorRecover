# RazorRecover

Intelligent recovery of failed payment transactions.

## Architecture

High-level flow:

```
Payment Failure
      ↓
API / Ingestion
      ↓
Context Fetchers
      ↓
ML + RAG + LLM
      ↓
Policy / Safety Shield
      ↓
Execution
      ↓
Audit / Monitoring
```

Design principle:

> **The LLM recommends a recovery action. The deterministic Policy Engine authorizes it. The Execution Layer performs it.**

## Project structure

```
RazorRecover/
├── .github/          # CI/CD workflows and issue/PR templates
├── docs/             # Architecture and API documentation
├── docker/           # Containerization
├── scripts/          # Data generation, model training, seeding
├── src/razor_recover/
│   ├── api/          # API and transport layer
│   ├── fetchers/     # Context retrieval services
│   ├── brains/       # ML, RAG, and LLM intelligence
│   ├── shield/       # Deterministic safety and policy enforcement
│   ├── execution/    # Execution of approved recovery actions
│   ├── core/         # Infrastructure and shared services
│   ├── schemas/      # Request/response validation
│   └── db/           # Persistence layer
└── tests/            # Automated testing
```

## Status

Initial project scaffold only. No business logic implemented yet.
