# Contributing to Telegram Bulk Uploader

Thank you for your interest in contributing to **Telegram Bulk Uploader**! We welcome bug reports, feature requests, documentation improvements, and pull requests.

---

## 🛠️ Development Setup

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/<your-username>/telegram-bulk-uploader.git
   cd telegram-bulk-uploader
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   # Windows:
   .\.venv\Scripts\activate
   # macOS / Linux:
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

4. **Run unit tests:**
   ```bash
   python -m unittest discover -s tests -v
   ```

---

## 🐛 Reporting Bugs

Before creating an issue, please search existing issues to see if it has already been reported.

When filing a bug report, please include:
- Operating System & Python version (`python --version`)
- Exact error message or stack trace
- Steps to reproduce the behavior
- Whether the issue occurred in the Web UI or CLI

---

## 💡 Proposing Features

Feature ideas are always welcome! Please open an issue labeled **Feature Request** and explain:
- The problem or use-case you are trying to solve.
- How you envision the feature working (UI changes, CLI flags, configuration options).
- Any alternatives you've considered.

---

## 📥 Submitting Pull Requests

1. **Branch naming:** Create a feature branch with a descriptive name:
   ```bash
   git checkout -b feature/my-new-feature
   # or
   git checkout -b fix/issue-description
   ```

2. **Follow code style & guidelines:**
   - Keep code clean, readable, and typed where appropriate.
   - Respect Telegram's rate-limiting principles (never hardcode 0-second delays).
   - Ensure all unit tests pass before submitting (`python -m unittest discover -s tests -v`).
   - Add new test cases in `tests/test_uploader.py` for new functionality.

3. **Open the PR:**
   - Provide a clear summary of what changes were made and why.
   - Reference any related issues (e.g., `Closes #12`).

---

## ⚖️ Code of Conduct

Please be respectful, collaborative, and constructive when interacting with community members, maintainers, and contributors.
