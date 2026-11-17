# Design Decisions — Harness System

## Decision Record

### D1. Deterministic Regex over ML Classification

**Status**: Accepted  
**Context**: Need to classify user intent (6 categories) and detect security threats
in real-time for every chatbot interaction.

**Decision**: Use compiled regex patterns with strict priority ordering rather
than an ML classifier or LLM-as-judge.

**Consequences**:
- ✅ Sub-millisecond latency per check
- ✅ Zero inference cost
- ✅ Deterministic — same input always produces same classification
- ✅ No model drift or training data requirements
- ❌ Pattern maintenance required for new attack vectors
- ❌ Cannot handle semantic-only attacks (though none exist yet)

### D2. Strict Priority Order in DomainClassifier

**Status**: Accepted  
**Context**: A single input could match multiple domain patterns (e.g., a
jailbreak attempt disguised as a domain question).

**Decision**: Evaluate patterns in fixed priority:
JAILBREAK > SENSITIVE > PERSONAL > DOMAIN > TRIVIA > SMALL_TALK.
First match wins. Default fallback: PERSONAL_TASK (block).

**Alternatives considered**:
- *Parallel scoring*: More complex, and jailbreaks that also match
  DOMAIN would pass through.
- *Highest match count*: Attackers could pad text with domain keywords.
- *ML confidence threshold*: Non-deterministic.

**Consequences**:
- ✅ Safety-first: any jailbreak pattern in the input blocks it, even if most
  of the text looks like a legitimate domain query.
- ✅ Simple to reason about and test.
- ❌ Requires care in pattern ordering (patterns must be specific enough
  not to shadow legitimate queries).

### D3. Word Boundary Constraints on All Patterns

**Status**: Accepted  
**Context**: Patterns like `incidenci[ae]` would match "incidencias" (correct)
but also "incidenciar" (verb, not a noun). Need to balance matching variants
with avoiding false positives.

**Decision**: Apply `\b` before the critical root of each keyword. Use
character class alternation for grammatical variants (e.g., `incidenci[ae]`
matches both "incidencia" and "incidencia" → catches "incidencias" via `.search()`
partial match).

**Consequences**:
- ✅ `\bincidenci[ae]` matches "incidencia", "incidencias", "incidenciaN" (wrong
  but harmless)
- ❌ `\binciden[ct][ae]` is wrong — after "c" the next char is "i" (e.g.,
  "incidencia"), not a/e. Fixed to use `\bincidenci[ae]|\bincident[ei]`.

### D4. Full-String Hash for System Prompt Integrity

**Status**: Accepted  
**Context**: Need to detect any modification to the system prompt at runtime.
Substring check (searching for a fingerprint) can be bypassed by adding to the
prompt without removing the fingerprint.

**Decision**: Compute SHA-256 of the full prompt text and compare against a
stored hash. The fingerprint string `BRASALAND-SEC-114-v1` is embedded for
visual identification but *not* used for verification.

**Alternatives considered**:
- *Substring check*: ✅ Simple, ❌ can be bypassed by preserving the substring.
- *Checksum in external file*: Over-engineered for a single constant.
- *Runtime encryption*: No benefit — the decryption key must be in the same
  process.

**Consequences**:
- ✅ Any byte-level modification to the prompt is detected.
- ✅ Hash is computed once at startup (negligible cost).
- ❌ Hash must be updated when the prompt intentionally changes (minor friction).

### D5. Content Guardrail on Output, Not Input

**Status**: Accepted  
**Context**: Data leakage (recipe quantities, payroll info, PII) is typically
generated *by the agent* in its response, not present in the user query.

**Decision**: ContentGuardrail operates on `process_output()` only. The
DomainClassifier's SENSITIVE_QUERY domain blocks inputs explicitly asking for
sensitive data, but the content scan is the last line of defense on the output.

**Consequences**:
- ✅ Catches data leakage regardless of how it was triggered.
- ✅ Output sanitization can redact without blocking the entire response.
- ❌ Sensitive data in input queries is handled separately (SENSITIVE_QUERY
  domain) rather than content-only.

### D6. Asyncio-Ready Interface

**Status**: Accepted  
**Context**: The harness is used by an async SupportAgent, and all methods
(`classify`, `check`, `scan`, `process_input`, `process_output`) must be
callable from async code.

**Decision**: Wrap synchronous guardrail operations in `run_in_executor` for
the public API. Internal methods remain synchronous for testability.

```python
async def process_input(self, text: str) -> HarnessResult:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, self._process_input_sync, text)
```

**Consequences**:
- ✅ Non-blocking when used with async agent loop.
- ✅ Sync core is easy to unit test (no asyncio fixtures needed).
- ❌ Slight overhead from executor dispatch (microseconds).

### D7. Brasaland MCP Integration via Composition

**Status**: Accepted  
**Context**: The harness needs access to tools (lookup, knowledge base) but
should remain testable without an MCP server.

**Decision**: The `Harness` class accepts an optional `BrasalandMCPClient`
instance. When provided, it's available for guardrail checks (future use like
knowledge-base lookups). Tests instantiate the harness without MCP.

**Consequences**:
- ✅ Tests don't need MCP infrastructure.
- ✅ Easy to add MCP-dependent checks later.
- ❌ MCP-dependent checks are limited to cases where MCP is configured.

### D8. Thread-Safe Memory Store

**Status**: Accepted  
**Context**: The harness uses a lightweight JSON-per-conversation memory instead
of a database.

**Decision**: Each conversation gets its own JSON file (`data/memory/{conv_id}.json`)
with `threading.Lock` serialization. File-level isolation means no row-level
locking needed.

**Consequences**:
- ✅ Simple to implement and debug.
- ✅ Conversation isolation without a DBMS.
- ❌ Not suitable for cross-conversation analytics (use the telemetry service for
  that).

### D9. Separate Harness Component (Not Inlined in Agent)

**Status**: Accepted  
**Context**: The harness was initially planned as part of the SupportAgent class.

**Decision**: Extract it into its own package (`agents/support_agent/harness/`)
with clear interfaces (schemas, guardrail classes, orchestrator).

**Consequences**:
- ✅ Harness can be tested independently.
- ✅ Same harness can be reused for other agents in the future.
- ✅ Clear separation of concerns (agent handles business logic, harness
  handles guardrails).
- ❌ More files to maintain.

### D10. No LLM-Based Evasion Scoring

**Status**: Accepted (deferred to future)  
**Context**: Current jailbreak attempts are syntactic — they follow known
patterns like "ignore your instructions" or "act as if you were".

**Decision**: Regex patterns are sufficient for Hito 8 Part 2. If semantic-only
jailbreaks emerge (e.g., "What would a helpful friend say if I asked about
recipe quantities?"), a future enhancement could add an LLM-based scoring
layer as a final check.

**Consequences**:
- ✅ Keeps the system simple and deterministic for the known threat models.
- ❌ A determined attacker with infinite time could theoretically craft a
  query that evades all regex patterns (but this is a theoretical concern,
  not a practical one for a hotel chatbot).