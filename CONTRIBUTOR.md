# Contributors

Thanks to everyone who has contributed to Lytrize! This file acknowledges the people and contributions that have helped shape the project.

---

## Core Team

### Kazake95 — Creator & Lead Developer

- Designed and built the entire application architecture
- Streamlit backend with 11 chart types and dashboard builder
- PySide6 desktop launcher with browser isolation and crash recovery
- SQLite database layer with session management and auto-save
- Cross-platform packaging (.deb, .rpm, Windows .exe via Inno Setup 7)
- Offline font bundling and HTML export system
- Auto-update on re-upload with transform log preservation

---

## How to Contribute

Lytrize is open source and welcomes contributions from everyone. Here is how you can help:

### Reporting Bugs

1. Check if the issue already exists in the [issue tracker](https://github.com/Kazake95/lytrize_desktop/issues).
2. If not, open a new issue with:
   - A clear description of the problem
   - Steps to reproduce
   - Your operating system (Linux distribution or Windows version)
   - The Lytrize version (check `backend/config.py` or the About section in the app)
   - Relevant log output (backend log at `~/.local/share/lytrize/streamlit.log` on Linux, `%APPDATA%\Lytrize\streamlit.log` on Windows)

### Suggesting Features

1. Open an issue describing the feature you would like to see.
2. Explain the use case and why it would be valuable.
3. If you have ideas for implementation, include them in the description.

### Code Contributions

1. **Fork** the repository on GitHub.
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/lytrize_desktop.git
   cd lytrize_desktop
   ```
3. **Set up your development environment** — see [CONTRIBUTING.md](./CONTRIBUTING.md#development-setup) for full instructions.
4. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/my-feature
   ```
5. **Make your changes** following the code style and conventions in [CONTRIBUTING.md](./CONTRIBUTING.md#code-style-and-conventions).
6. **Test** your changes on your platform:
   ```bash
   streamlit run backend/app.py
   ```
7. **Commit** with a clear, descriptive message:
   ```bash
   git commit -m "Add feature: description of changes"
   ```
8. **Push** to your fork:
   ```bash
   git push origin feature/my-feature
   ```
9. **Open a Pull Request** against the `main` branch.

### Documentation

Improvements to documentation are always welcome:

- Fix typos or unclear instructions in README.md or CONTRIBUTING.md
- Add examples or screenshots
- Translate documentation to other languages
- Improve code comments and docstrings

### Testing

- Test bug fixes and new features on your platform
- Report any regressions you find
- If possible, test on both Linux and Windows

---

## Contribution Guidelines

- Keep PRs focused — one change per PR
- Follow the existing code style and naming conventions
- Update documentation if your change affects user-facing behavior
- Ensure the app runs: `streamlit run backend/app.py`
- Mention testing steps in your PR description
- Be respectful and constructive in all interactions

---

## Development Platforms

Lytrize is developed and tested on:

- **Linux:** Ubuntu 20.04+, Fedora, Debian-based distributions
- **Windows:** Windows 10/11 (64-bit)

Contributions that improve compatibility with other platforms (e.g., macOS) are welcome, though the primary focus is Linux and Windows.

---

## License

By contributing to Lytrize, you agree that your contributions will be licensed under the MIT License. See [LICENSE](./LICENSE) for the full text.
