# Product Implementation Matrix

| Capability | Backend | Product UI | Tests | Status |
|---|---|---|---|---|
| Workspace access + isolation | Workspace-token auth; per-workspace DB | Access-key sign-in | two-key isolation | Implemented |
| Contract TXT/MD/DOCX/PDF/paste | ingestion + source hashes | upload/paste | paste + DOCX; parser unit coverage | Implemented |
| LLM contract proposal | native constrained Gemini compiler | Analyze contract | compiler/generalization suites | Implemented |
| Exact source binding | span + text hash | source-to-rule review | native compiler tests | Implemented |
| AIR compiler assurance | grounding, coverage, predicate, settlement, execution, mutation gates | Advanced assurance + approval block | AIR suite | Implemented |
| Human AIR approval/versioning | immutable versions + supersession | review + approve | persistence/immutability | Implemented |
| Invoice import/mapping | preview + aliases + explicit mapping | mapping step | product mapping test | Implemented |
| Evidence ingestion | CSV/JSON/JSONL + raw provenance | upload + completeness declaration | upload suite | Implemented |
| Identity matching/review | authoritative vs suggested/manual | manual review | matching suite | Implemented |
| Evidence capability plan | conservative auto inference | readiness warning | agreement runtime tests | Implemented |
| Atomic predicate facts | persisted predicate IDs/hashes + deterministic derivation | Advanced facts | agreement runtime tests | Implemented |
| Deterministic AIR adjudication | generic AIR evaluator | Run reconciliation | no-LLM + generalization tests | Implemented |
| Needs-review behavior | explicit unknown/conflict handling | exception warning + rerun | product smoke | Implemented |
| Line provenance | contract clauses + evidence timeline | determination table | sample product test | Implemented |
| Append-only reruns | run version/supersedes | rerun action | upload suite | Implemented |
| Finance exports | corrected CSV, disputes CSV, summary/evidence JSON, HTML report | download actions | export smoke | Implemented |
| Audit log | persisted action history | Advanced history | export audit test | Implemented |
| One-click sample | deterministic seed | Try sample workspace | product smoke | Implemented |
| Fresh-checkout validation | bootstrap/dev-check/product-smoke | n/a | release gate | Implemented; requires registry availability |
