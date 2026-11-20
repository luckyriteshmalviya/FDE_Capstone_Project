# CloudServe Stage 5 — A1–A12 Acceptance Audit

Audit date: 2026-11-20. Updated after A11 fault-injection verification. Basis: official `02_Build_Specification.docx`, original Stage 5 ZIP, inspected code, local regression tests and 80-ticket evaluation. This is a **pre-submission evidence audit**, not a claim of an independent assessor's final verdict.

Status semantics: **PASS (local)** = directly demonstrated by tests or local execution; **NOT VERIFIED** = missing a required test or independent evidence; **FAIL** = a demonstrated shortcoming relative to the stated requirement. Each official criterion is ultimately judged pass/fail.

| Criterion | Status | Evidence | Remaining gap / action |
|---|---|---|---|
| A1 Clean checkout | NOT VERIFIED | README documents Python environment, installation, pytest, harness and API; user reports successful Windows execution | Clone into a *new empty directory*, install exactly as documented, run tests, API and harness. No actual fresh Git clone evidence supplied. |
| A2 Four channels | PASS (local) | `tests/test_pipeline.py::test_channels` parametrized for `email`, `chat`, `docs_comment`, `forum`; normalization in `src/pipeline.py` | Repeat four API requests as evaluator would. |
| A3 Intent, urgency, confidence | PASS (local) | `test_classification`, `Pipeline.classify`; output numeric confidence within [0,1] | Probabilities are **uncalibrated**; manual examples have low confidence. Calibration and out-of-sample quality are concerns. |
| A4 Corpus retrieval and traceable passages | PASS (local) | `test_retrieval_sources_resolve`; `Pipeline.retrieve` uses actual `documentation.json` with stable passage IDs and scores | Passage relevance is imperfect; headings may rank highly. |
| A5 Threshold and deterministic route | PASS (local) | `test_deterministic_route`; explicit `confidence_threshold=.28` and `retrieval_threshold=.105` | Threshold is provisional and needs calibration rationale. |
| A6 Cited generated answers | PASS (local) | `Pipeline.validate` checks citation membership and exact excerpt in cited passage; `test_generated_answer_is_verbatim_when_sent`, `test_unsupported_excerpt_blocked` | Only applies to offline extractive answer format; no human semantic accuracy evaluation. |
| A7 Blocking guardrail | PASS (local) | `test_prompt_injection_blocked`; API injection request returns `status=blocked`, `answer=null` | Validation-set count of blocked tickets is 0; separate adversarial test demonstrates activation. |
| A8 Persistent decision logging | PASS (local) | Harness writes one `decisions.jsonl` entry per input; patched API writes `api_decisions.jsonl`; `test_api_persistent_log_and_message_alias` | Verify logging path permissions in clean checkout. No log rotation or retention policy yet. |
| A9 Unattended full evaluation | PASS (local validation) | `python -m evaluation.harness --input data/validation_tickets.json --output evaluation/results/` completes 80/80; `test_full_batch`; path is configurable | **Hidden 120-ticket run NOT VERIFIED**, since hidden file is not supplied. |
| A10 Automatic metrics report | PASS (local) | `evaluation/results/metrics.json` includes volume, business, technical and governance measures; computed by harness | True FCR and customer response time cannot be measured: now explicitly null / labeled as proxy; retrieval hit is threshold-based not human relevance. |
| A11 Graceful failure | PASS (local fault injection) | `tests/test_failure_handling.py`: simulated classifier timeout/outage, retrieval rate-limit exception, validator outage, malformed input, and per-ticket batch crash; all safely escalate without unsupported answers; batch continues | Offline implementation has no external provider: synthetic rate-limit test does **not** prove HTTP 429 retries, backoff, or recovery. |
| A12 Single-command tests | PASS (local) | `python -m pytest tests/ -q`: **23 passed** | Re-run from clean checkout. |

## Corrected measured metrics

- Processed: **80/80**; complete run: **true**.
- Answered automatically: **47 (58.75%)**; escalated: **33 (41.25%)**; guardrail blocks in validation: **0**.
- Retrieval hit rate: **95.0%** (threshold hit, not independently validated relevance).
- Citation-resolution rate for generated extractive answers: **100%** (automated verification, not human answer quality).
- Routing agreement with supplied expected route: **68.75%**; investigate this before claiming business success.
- First-contact resolution: **not measurable** from offline response decisions; `first_contact_resolution_pct: null`.
- Local latency P95: see `evaluation/results/metrics.json`; not equivalent to actual customer response time.
- Classification accuracy on supplied 80 validation tickets: **100%**; manual out-of-sample requests show weaker confidence. Avoid claims of generalization.

## Fixes in this audited version

1. API request decisions persisted to JSONL, configured by `CLOUDSERVE_DECISION_LOG`.
2. API supports `message` as a body alias, with `body` preferred.
3. Offline extractive grounding checks that the cited excerpt appears verbatim in the cited source.
4. `validation.performed` distinguishes skipped from executed validation.
5. `automatic_answer_rate_pct` added; `first_contact_resolution_pct` set to `null` until outcome evidence exists.
6. Four audit regression tests plus six A11 fault-injection tests; **23/23 tests pass**. Full validation counts remain 47/33.

## Mandatory remaining actions before submission

1. Reproduce from a genuinely fresh Git clone on Windows, recording commands and outputs.
2. A11 local fault-injection tests added and passed; document that provider-specific resilience is not applicable to this offline baseline.
3. Run one API ticket from each of four channels, a grounded auto-answer, and an adversarial blocked ticket; save responses for video.
4. Review 68.75% routing agreement and answer relevance. Do not optimize only for auto-answer rate.
5. Complete fairness, governance, attribution, Git history, final report, video and submission package.

## How to run

```powershell
python -m pip install -r requirements.txt
python -m pytest tests/ -v
python -m evaluation.harness --input data/validation_tickets.json --output evaluation/results/
python -m src.api
```

`GET /health`, `POST /tickets/process`, and Swagger UI `/docs` are available on localhost port 8000.
