# CloudServe AI Support Automation — IIT Roorkee FDE Capstone Stage 5

A reproducible **offline baseline** for support-ticket classification, TF-IDF knowledge retrieval, deterministic routing, extractive grounded answers, safety validation, and unattended evaluation. **No LLM provider is called.** Do not describe this as an LLM-generated system. It intentionally trades generative fluency for reproducibility and low cost.

## Requirements
Python 3.11 or 3.12 recommended.
No API key required. 
Run commands from the repository root.

### Windows PowerShell
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m pytest tests/ -v
python -m evaluation.harness --input data/validation_tickets.json --output evaluation/results/
python -m src.api
```

### macOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python -m pytest tests/ -v
python -m evaluation.harness --input data/validation_tickets.json --output evaluation/results/
python -m src.api
```

API: `GET http://127.0.0.1:8000/health` and `POST http://127.0.0.1:8000/tickets/process`. API docs: `http://127.0.0.1:8000/docs`.

The evaluation command accepts **any input JSON array**, including an unseen hidden test file, and writes `decisions.jsonl`, `results.json`, and `metrics.json` to the requested output directory. It does not require manual intervention. Every input record gets an output record.

## Design
1. `normalize`: handles all four channels and missing fields.
2. `classify`: two reproducible TF-IDF + logistic regression models trained on supplied 500 development tickets. Scores are *uncalibrated* probabilities; calibration is reported, not asserted.
3. `retrieve`: TF-IDF cosine similarity over heading-separated passages of 29 supplied documents, with a relevance cutoff and traceable passage IDs.
4. `route`: explicit safety restrictions, sensitive intents, risk keywords, confidence threshold, and retrieval threshold.
5. `generate`: extractive quotation of documentation with passage citation; no ungrounded LLM text.
6. `validate`: detects email, phone-like patterns, secrets, and invalid/missing citations. Failed checks block release.
7. `evaluation`: durable per-ticket JSONL log and automatic metrics.

## Limitations and evaluation honesty
- The classifier uses 500 labeled development tickets. Confidence is not calibrated, and a threshold of 0.28 is a provisional heuristic, not a validated operating point.
- Grounding is constrained by extractive generation, but **human assessment of hallucination and citation support is still required**. Citation existence is not citation accuracy.
- Offline automated answers do not establish real-world first-contact resolution or CSAT. Processing latency is not actual customer first-response time.
- `labels.must_not_auto_respond` is used as a safety flag when provided by the dataset; production would need an independent policy engine because hidden evaluation labels may not exist.
- Human review of at least 50 answers by two independent reviewers, fairness checks, and a provider outage simulation with a real provider are outstanding.
- No git history is included in this generated archive; initialize and commit to a real repository before submission.

## Demonstration examples
```bash
python -m evaluation.harness --input data/validation_tickets.json --output evaluation/results/
python -m pytest tests/ -v
```

## Stage 5 acceptance audit (2026-11-20)

See `ACCEPTANCE_AUDIT.md` for the A1–A12 evidence matrix, remaining gaps and the measured limitations. API decisions are appended to `evaluation/results/api_decisions.jsonl` by default; set `CLOUDSERVE_DECISION_LOG` to override. `message` is accepted as an alias for `body`. `first_contact_resolution_pct` is intentionally `null` because customer resolution is not observed; use `automatic_answer_rate_pct` for the measured automation rate.
