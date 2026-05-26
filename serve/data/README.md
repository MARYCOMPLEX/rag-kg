# data/ — Library Data & Evaluation Sets

Each Library is a self-contained directory under `data/libraries/<library_id>/`.

## Directory Structure

```
data/libraries/<library_id>/
├── corpus/                    # Raw source documents (PDFs, etc.)
│   ├── spike/                 # Initial 5-10 papers for pipeline validation
│   └── full/                  # Full corpus (hundreds to thousands)
├── evals/                     # Evaluation sets (auto-generated + human-curated)
│   ├── qa.smoke.v1.yaml       # 10-question smoke test (auto-generated, then human-reviewed)
│   ├── qa.multihop.v1.yaml    # 30-question multi-hop set
│   └── review.v1.yaml         # 5-topic review generation set
└── meta.yaml                  # Library metadata (name, description, domain, created_at)
```

## Conventions

- **corpus/** is gitignored (large binary files). Back up separately.
- **evals/** is tracked in git (small YAML files, version-controlled).
- **meta.yaml** is tracked in git.
- Eval sets are auto-generated after ingestion via `rkb eval generate --library <id>`.
- Human-validated samples are marked `human_validated: true` in YAML.
- At least 50% of smoke set samples should be human-validated before use as CI gate.

## Eval Auto-Generation Flow

```
ingest corpus → chunk + embed → LLM generates QA pairs from chunks
                                    ↓
                              qa.smoke.v1.yaml (draft, human_validated: false)
                                    ↓
                              human review → mark human_validated: true
                                    ↓
                              ready for CI gate
```
