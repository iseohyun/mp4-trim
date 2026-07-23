# Contributing to MP4-Trim

Thank you for your interest in contributing to **MP4-Trim**! 🎉
MP4-Trim is an open-source, lossless MP4 video cutter and player built with Python & PyQt6.

This project is licensed under the **GNU General Public License v3.0 (GPLv3)**. By contributing, you agree that your contributions will also be licensed under the GPLv3.

---

## 📜 Principles & Open Source License Policy

- **Strong Copyleft (GPLv3)**: All code in this repository and any future forks, modifications, or derivatives **MUST remain open source**. Private or proprietary closed-source distribution of derived works is strictly prohibited under the license.
- **Transparence & Quality**: Every change must maintain code readability, pass unit & traceability tests, and follow PEP 8 Python coding standards.

---

## 🛠️ How to Contribute

### 1. Reporting Bugs & Requesting Features
If you find a bug or have a feature suggestion, please open an Issue with:
- A clear, descriptive title.
- Steps to reproduce the bug (including OS version, video specs if applicable).
- Expected behavior vs actual behavior.
- Error logs or tracebacks if available.

### 2. Setting Up Local Development
1. **Fork and Clone the Repository**:
   ```bash
   git clone https://github.com/your-username/mp4-trim.git
   cd mp4-trim
   ```
2. **Install Dependencies**:
   ```bash
   pip install PyQt6 pyinstaller
   ```
3. **Run the Application**:
   ```bash
   python mp4-trim.py
   ```

### 3. Running Automated Tests
Before submitting any Pull Request, ensure that all automated unit and traceability tests pass cleanly:
```bash
python test_requirements_trace.py
```
*(All 9 traceability tests must return `[PASS]`).*

### 4. Submitting a Pull Request (PR)
1. Create a new topic branch:
   ```bash
   git checkout -b feature/amazing-new-feature
   ```
2. Make your code changes cleanly. Follow PEP 8 standards.
3. Commit your changes with concise commit messages following Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`).
4. Push to your fork and submit a **Pull Request** to `main`.
5. Clearly describe the changes and motivation in your PR description.

---

## 🤝 Code of Conduct
Please be respectful and constructive in all issue discussions and code reviews. Let's make video editing faster and simpler for everyone!
