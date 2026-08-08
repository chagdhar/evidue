python - <<'PY'
from pathlib import Path

path = Path("backend/app/agreements/native_compiler.py")
text = path.read_text()

text = text.replace(
    'NATIVE_COMPILER_VERSION = "native-air-0.2"',
    'NATIVE_COMPILER_VERSION = "native-air-0.3"',
    1,
)

text = text.replace(
    'NATIVE_PROMPT_VERSION = "native-air-prompt-0.2"',
    'NATIVE_PROMPT_VERSION = "native-air-prompt-0.3"',
    1,
)

path.write_text(text)
print("Bumped native compiler provenance to 0.3")
PY
