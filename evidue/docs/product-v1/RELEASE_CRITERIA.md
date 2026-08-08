# Product v1 Release Criteria

A release candidate is acceptable only when a fresh workspace can:

- create/load a vendor agreement and approved AIR;
- ingest an invoice and evidence;
- deterministically reconcile it;
- produce stable input/calculation hashes across identical reruns;
- surface every `needs_review` determination as a review case;
- retain the machine result after human review;
- block finance approval while review exposure remains;
- approve the final payable after complete disposition;
- open a dispute only from an approved settlement;
- progress a dispute through validated lifecycle transitions;
- export a printable vendor dispute package;
- reset the workspace without orphaning product records;
- pass backend, frontend, build, and E2E validation from a fresh checkout.
