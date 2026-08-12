# Normal User Acceptance Checklist

A release is product-usable only if all answers below are yes without terminal/database intervention during the workflow.

- [x] A user understands the purpose from `/workspace` before uploading anything.
- [x] The empty state offers a safe sample workspace and a real-data path.
- [x] A contract can be uploaded or pasted in a common supported format.
- [x] The user can see what the compiler interpreted and the exact source clause behind it.
- [x] Failed assurance/conformance prevents approval with a useful error.
- [x] An arbitrary invoice CSV can be mapped without renaming columns externally.
- [x] Evidence completeness is an explicit operator choice, not inferred from missing rows.
- [x] Non-authoritative identity matches cannot silently affect money.
- [x] Reconciliation works after all model access is disabled.
- [x] Payable, disputed, and needs-review amounts are visibly separate.
- [x] A disputed/review line explains why, shows contract source, and shows decisive evidence.
- [x] Adding evidence and rerunning creates a new run rather than overwriting history.
- [x] Finance can download a corrected invoice and review artifact.
- [x] A second workspace key cannot see the first workspace's data.
- [x] Refreshing the browser reloads persisted workspace state.

## Validation note

The product/API smoke validates the workflow and outputs without model access during reconciliation. Browser source and Playwright coverage are updated for the same first-time-user path. In the current build environment the frontend dependency install cannot execute because the forced npm mirror does not contain `yocto-queue@0.1.0`; run `./scripts/dev-check.sh full` on a network/registry-capable machine before deployment.
