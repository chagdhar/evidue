# Audit and Reproducibility Model

Audit events record organization/vendor creation, reconciliation completion, review creation/decision, finance approval, dispute creation, and dispute transitions.

## Trust chain

```text
approved AIR payload hash
+ agreement source bundle hash
+ verification plan hash
+ raw evidence payload hashes
+ identity/manual-match/fact inputs
= input_manifest_hash

input_manifest_hash
+ deterministic determination outputs
= kernel calculation_hash

kernel calculation_hash
+ append-only review overlay
+ final payable/disputed/open-review amounts
= settlement calculation_hash
```

An approval copies the settlement calculation hash. The UI exposes all three fingerprints through the reconciliation trust endpoint.
