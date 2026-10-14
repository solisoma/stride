# Backend development rules

- Remove unused imports whenever changing code.
- Before finishing backend changes, run `uv run ruff check . --select F401`.
- Preserve imports that intentionally expose public APIs; mark explicit re-exports.
