# Unified Finding Schema

All KitTools review agents emit findings in this shape, written as JSON to `{{RESULT_FILE_PATH}}` by the agent and read by the calling skill. This lets skills orchestrate multiple reviews with a single parser instead of one format per agent.

## Result File Format

```json
{
  "review_type": "code-quality|security|feature-compliance|drift|template-validation|story-quality|spec-completeness|spec-second-opinion|spec-security|salty-engineer|codebase-fit|test-optimizer|vision-*",
  "target": "<what was reviewed — file path, doc name, spec name, template name>",
  "overall_verdict": "clean|warnings|issues",
  "canonical_verdict": "ready|needs-work|not-ready",
  "findings": [
    {
      "severity": "critical|warning|info",
      "category": "<agent-specific category>",
      "location": "<file, file:line, section name, or identifier>",
      "description": "<specific, evidence-based observation>",
      "recommendation": "<actionable fix>"
    }
  ],
  "summary": "<one-sentence overall assessment>"
}
```

## Field Rules

| Field | Required | Notes |
|-------|----------|-------|
| `review_type` | yes | Fixed string identifying the agent kind — skills use this to route findings |
| `target` | yes | Free-form; what the agent evaluated |
| `overall_verdict` | yes | Derived from findings: `clean` if no findings, `warnings` if only info/warning, `issues` if any critical |
| `canonical_verdict` | yes | The cross-agent verdict vocabulary: `clean`→`ready`, `warnings`→`needs-work`, `issues`→`not-ready`. Always emitted alongside the native field — see "Canonical Verdict" below |
| `findings` | yes | Empty array `[]` when clean |
| `findings[].severity` | yes | `critical` blocks shipping, `warning` should be addressed, `info` is a heads-up |
| `findings[].category` | yes | Free-form within agent's domain (e.g., `injection`, `naming-convention`, `stale-file`) |
| `findings[].location` | yes | Specific enough to locate: `src/auth.ts:42`, `US-003 criterion 2`, `arch/CODE_ARCH.md § Tech Stack` |
| `findings[].description` | yes | Quote the evidence where possible; no "I think" or "might be" |
| `findings[].recommendation` | yes | Concrete; what to change, not what to avoid |
| `summary` | yes | One sentence; readable in isolation |

## Optional Domain-Specific Fields

Agents may add fields beyond the core set. Skills ignore unknown fields.

- `confidence: high|medium|low` — used by `test-optimizer` and `drift-detector` where findings are heuristic
- `trade_offs: "<what the alternative gains/sacrifices>"` — required by `spec-second-opinion` for alternative-approach and over-engineering categories
- `evidence: {claim: "<doc says>", reality: "<code shows>"}` — `drift-detector` uses this to surface the specific divergence. `codebase-fit-reviewer` uses a variant: `{existing_code: "<path:line — what exists>", spec_proposes: "<what the spec plans instead>"}`
- `code_snippet: "<relevant lines>"` — optional for code reviewers when the snippet adds clarity

## Verdict Derivation

Skills may derive `overall_verdict` from findings rather than trusting the agent's self-report:

- `findings` is empty → `clean`
- Any finding with `severity: critical` → `issues`
- Otherwise → `warnings`

The agent-emitted `overall_verdict` should match this derivation. Mismatches (agent says `clean` but has critical findings) are bugs and should be flagged.

## Canonical Verdict (cross-agent vocabulary)

KitTools agents historically used five verdict vocabularies (this schema's `clean|warnings|issues`, spec reviewers' `ready|needs-work|not-ready`, vision reviewers' 1–5 scores, the implementer's `complete|partial|failed`, the verifier's `pass|pass_with_warnings|fail`). Every consumer had to normalize ad hoc.

`canonical_verdict: ready|needs-work|not-ready` is the single vocabulary **every verdict-bearing agent emits in addition to its native field** (native fields stay — this is additive, so existing consumers keep working). Standard mappings:

| Agent family | Native | → canonical_verdict |
|---|---|---|
| Finding Schema emitters | `clean` / `warnings` / `issues` | `ready` / `needs-work` / `not-ready` |
| Spec reviewers | already `ready\|needs-work\|not-ready` | same value, mirrored |
| Vision reviewers (completionist, feasibility) | dimension scores | all ≥ 4 → `ready`; any < 3 → `not-ready`; else `needs-work` |
| Vision readiness reviewer | `overall_readiness` (already canonical) | same value, mirrored |
| story-implementer | `complete` / `partial` / `failed` | `ready` / `needs-work` / `not-ready` |
| story-verifier | `pass` / `pass_with_warnings` / `fail` | `ready` / `needs-work` / `not-ready` |
| feature-fixer | all fixed / some unfixable / none fixed | `ready` / `needs-work` / `not-ready` |

Consumers (skills, hooks, the supervisor) should prefer `canonical_verdict` for new aggregation logic and fall back to the native field when reading results produced by pre-2.7.0 agents.

## Why This Schema Exists

Before v2.4.0, review agents emitted different text-block formats (`FINDING:/END_FINDING`, `DRIFT:/END_DRIFT`, `ISSUE:/END_ISSUE`, and several JSON variants). Skills had to know each agent's format. Adding a new review dimension meant writing a new parser. This schema consolidates to one shape so skills orchestrate findings without caring which agent produced them.
