# Contributing

## Development Environment

- Python: `3.14`
- Formatter adapters currently covered: `clang-format`, `gofmt`, `ruff format`, `rustfmt`, `oxfmt`

## Local Checks

```powershell
ruff check LanguageFormat tests
python -m compileall LanguageFormat tests
python -m pytest
```

## Contribution Guidelines

- Keep the Sublime package runtime dependency-free.
- Prefer project-native formatter configuration over plugin-specific style translation.
- Add or update tests for discovery logic, command construction, and range handling when behavior changes.
- Keep docs in sync when adding languages, settings, or commands.
