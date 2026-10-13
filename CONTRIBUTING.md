# Contributing to proxy-check

Thank you for your interest in contributing to **proxy-check**! This project is an open-source tool designed to help developers and data engineers test and benchmark proxy lists fast and reliably.

---

## Development Setup

### Prerequisites

- Python 3.11+
- Git

### Initializing the Environment

1. Clone the repository:
   ```bash
   git clone https://github.com/Lunar-Dev17/Proxy-Checker.git
   cd Proxy-Checker
   ```

2. Create and activate a virtual environment:
   ```bash
   # On macOS/Linux:
   python -m venv .venv
   source .venv/bin/activate

   # On Windows:
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. Install the package in editable mode with development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

---

## Coding Standards & Linting

We use [Ruff](https://astral.sh/ruff) for linting and code formatting:

- **Check linting rules:**
  ```bash
  ruff check .
  ```
- **Auto-fix lint issues:**
  ```bash
  ruff check . --fix
  ```
- **Check formatting:**
  ```bash
  ruff format --check .
  ```
- **Auto-format code:**
  ```bash
  ruff format .
  ```

---

## Running Tests

All tests are written for `pytest` with mocked network calls to ensure fast, isolated, and deterministic test runs:

```bash
pytest -v
```

Ensure all existing tests pass and write new tests for any added features or bug fixes.

---

## Submitting Pull Requests

1. Fork the repository and create your branch from `main`:
   ```bash
   git checkout -b feature/my-new-feature
   ```
2. Commit your changes with descriptive commit messages.
3. Verify that all tests pass (`pytest`) and linting passes (`ruff check .` & `ruff format --check .`).
4. Push your branch to GitHub and open a Pull Request.

---

## License

By contributing to `proxy-check`, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).
