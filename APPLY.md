Extract this archive at the root of the existing Evidue repository.

    cd ~/dev/evidue
    tar -xzf ~/Downloads/evidue-lint-correctness-patch.tgz -C .
    uv run ruff check backend
    uv run pytest backend/tests/test_rule_compiler.py

The patch fixes UTC timestamps, duplicate RuleProgram, loop-closure binding, annotations, imports, and formatting.
