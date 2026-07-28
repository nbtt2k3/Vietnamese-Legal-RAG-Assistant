# Human Review Policy

The system marks answers for human legal review when the generated response should not be treated as a final legal conclusion without professional checking.

The signal is exposed in:

```text
answer.confidence.human_review_required
answer.confidence.human_review_reasons
```

## Review Triggers

- `no_retrieved_evidence`: no legal evidence was retrieved.
- `low_confidence`: retrieval or generation confidence is low.
- `legal_conflict_detected`: the generator detected conflicting legal grounds.
- `invalid_evidence_used`: the answer referenced evidence IDs that were not retrieved.
- `claims_without_evidence`: at least one claim has no valid evidence ID.
- `weakly_supported_claims`: at least one cited claim has weak textual support.
- `unverified_source`: at least one source is not officially verified.
- `unverified_validity`: at least one validity status is not officially verified.
- `fact_sensitive_legal_scenario`: the answer applies law to a factual scenario or case-law question.

## Usage Rule

When `human_review_required` is true, the frontend must show a review warning and the answer must not be presented as final legal advice.

This policy does not expand product scope. It only formalizes how existing confidence, citation, grounding, source, and validity signals are converted into a production safety gate.
