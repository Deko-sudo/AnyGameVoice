# Contributing to AnyGameVoice

Thank you for considering contributing! This project is community-driven.

## How to Contribute

### Report Bugs

1. Check existing issues first
2. Use the bug report template
3. Include: OS, Python version, GPU, steps to reproduce

### Suggest Features

1. Check the ROADMAP.md first
2. Open a feature request issue
3. Explain the use case

### Submit Code

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes
4. Run tests: `pytest tests/`
5. Commit with clear messages
6. Push to your fork
7. Open a Pull Request

### Create Plugins

See docs/plugin_development.md for the plugin API.

## Code Style

- Follow PEP 8
- Type hints required
- Docstrings for public functions
- Tests for new features

## Development Setup

```bash
git clone https://github.com/Deko-sudo/AnyGameVoice.git
cd AnyGameVoice
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## License

By contributing, you agree that your contributions will be licensed under Apache 2.0.
