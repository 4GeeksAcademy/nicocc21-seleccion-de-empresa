# Harness Architecture — Brasaland Support Agent

## Overview

The Harness is a multi-layer guardrail system for the Brasaland Support Agent
(Hito 8 — Part 2). It intercepts every user message *before* the agent processes
it and every agent response *before* it reaches the user, applying deterministic
regex-based checks that run in **O(n)** time with no external dependencies.

## Why Regex (Not LLM-as-Judge)?

| Criterion | Regex Guardrails | LLM-as-Judge |
|-----------|-----------------|---------------|
| Latency   | < 1 ms          | 500–3000 ms   |
| Cost      | $0              | ~$0.01/call   |
| Determinism | ✅ Always same | ❌ Probabilistic |
| Evasion hardness | High (no prompt to probe) | Low (leaked in training) |
| Maintainability | Simple file edits | Prompt engineering |

The four mandatory jailbreak cases (poem, recipe, cost extraction, gradual
extraction) are all **syntactic patterns** — they don't require semantic
understanding, only structural detection. Regex is the correct tool.

## Architecture

```
User Input
    │
    ▼
┌──────────────────────────────────────────────────────┐
│  HARNESS.process_input(text)                         │
│                                                      │
│  1. SecurityGuardrail.check(text)                    │
│     ┌─────────────────────────────────────────────┐  │
│     │ CRITICAL → BLOCK (direct jailbreak)         │  │
│     │ HIGH     → BLOCK (if block_on_high=True)    │  │
│     │ LOW/NONE → continue                         │  │
│     └─────────────────────────────────────────────┘  │
│                                                      │
│  2. DomainClassifier.classify(text)                  │
│     ┌─────────────────────────────────────────────┐  │
│     │ JAILBREAK         → BLOCK                   │  │
│     │ SENSITIVE_QUERY    → REDIRECT               │  │
│     │ PERSONAL_TASK      → BLOCK                  │  │
│     │ DOMAIN             → PASS                   │  │
│     │ TRIVIA             → REDIRECT               │  │
│     │ SMALL_TALK         → REDIRECT               │  │
│     └─────────────────────────────────────────────┘  │
│                                                      │
│  3. Return HarnessResult(action, safe_input, ...)    │
└──────────────────────────────────────────────────────┘
    │
    ├── BLOCK    → Return safe_input to user
    ├── REDIRECT → Return safe_input to user
    └── PASS     → Forward safe_input to SupportAgent
                      │
                      ▼
              SupportAgent processes
                      │
                      ▼
┌──────────────────────────────────────────────────────┐
│  HARNESS.process_output(response, input_result)      │
│                                                      │
│  4. ContentGuardrail.scan(response)                  │
│     ┌─────────────────────────────────────────────┐  │
│     │ RECIPE  → SANITIZE (redact quantities)       │  │
│     │ PRICING → SANITIZE                           │  │
│     │ PAYROLL → SANITIZE                           │  │
│     │ PII     → SANITIZE                           │  │
│     │ Clean   → PASS                               │  │
│     └─────────────────────────────────────────────┘  │
│                                                      │
│  5. Return updated HarnessResult                     │
└──────────────────────────────────────────────────────┘
```

## Priority Order

The DomainClassifier uses strict priority order (highest first):

1. **JAILBREAK** — Security threats, instruction override attempts
2. **SENSITIVE_QUERY** — Data extraction (recipes, prices, payroll, PII)
3. **PERSONAL_TASK** — Non-business tasks (homework, code, therapy)
4. **DOMAIN** — Business operations (incidents, inventory, procedures)
5. **TRIVIA** — General hospitality questions
6. **SMALL_TALK** — Greetings and pleasantries

If no pattern matches, the fallback is `PERSONAL_TASK` (block by default).

## Threat Levels (SecurityGuardrail)

| Level    | Action   | Description | Examples |
|----------|----------|-------------|----------|
| CRITICAL | BLOCK    | Direct instruction override | "Ignora tus instrucciones", "Override system prompt" |
| HIGH     | BLOCK*   | Boundary testing, role-play | "Actúa como si fueras...", "Repeat your prompt" |
| LOW      | LOG/WARN | Subtle probing | "Quién te programó?", "What else can you do?" |
| NONE     | PASS     | Benign input | Normal Brasaland operations |

\* HIGH can be configured to not block via `block_on_high=False`.

## Component Files

| File | Class | Purpose |
|------|-------|---------|
| `schemas.py` | — | Pydantic models for all results and enums |
| `security_guardrail.py` | `SecurityGuardrail` | Jailbreak / prompt injection detection |
| `domain_classifier.py` | `DomainClassifier` | Intent classification (6 domains) |
| `content_guardrail.py` | `ContentGuardrail` | Post-output data leak detection |
| `harness.py` | `Harness` | Orchestrator that chains all guardrails |
| `__init__.py` | — | Public exports |

## System Prompt Integrity

The system prompt is protected by a SHA-256 hash:

```python
SYSTEM_PROMPT_HASH = "1734d567..."  # SHA-256 of original prompt
```

`verify_system_prompt()` computes the hash of the current prompt and compares
it against the stored hash. Any modification (even one character) produces a
different hash, immediately detectable. The fingerprint string
`BRASALAND-SEC-114-v1` is embedded in the prompt text for quick visual
identification.

## Multi-Layer Design (Why Required)

The acceptance criteria demand **three distinct filtering layers**:

1. **Security layer** — Catches direct attacks (jailbreak, prompt injection)
2. **Domain layer** — Routes conversations to correct channel
3. **Content layer** — Prevents data leakage in agent responses

Each layer addresses a different threat vector. A single filter would fail
because:
- A personal task might be safe but out-of-domain
- A domain question might contain a jailbreak attempt
- A legitimate response might accidentally leak sensitive data

## Test Coverage

149 test cases covering:
- 25+ jailbreak variants (ES/EN, imperative/infinitive, with/without modifiers)
- 20+ domain classification scenarios (all 6 domains)
- 30+ security threat patterns (3 threat levels)
- 20+ content leakage scenarios (recipes, pricing, payroll, PII)
- System prompt integrity (fingerprint presence, hash verification)
- Edge cases (empty input, whitespace, unknown words, gradual extraction)
- Integration tests (full harness pipeline for each jailbreak case)