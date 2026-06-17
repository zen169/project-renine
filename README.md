# Renine

**A free, hybrid, local AI butler inspired by Friday from Iron Man.**

Renine is a Level 5 intelligent companion capable of natural voice and chat interaction, home management, long-term personal memory, file understanding, desktop control, coding assistance, and more.

## Status

**Current Phase:** Phase 1 — MVP Foundation  
**Version:** 0.1.0

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (package manager)
- [Ollama](https://ollama.ai/) with `qwen3:8b` model pulled
- NVIDIA GPU with CUDA (RTX 3060 12GB recommended)
- Windows 11

## Setup

```bash
# Clone the repository
git clone https://github.com/zen169/project-renine.git && cd project-renine

# Install dependencies with uv
uv sync

# Install dev dependencies
uv sync --extra dev

# Copy environment template
cp .env.example .env
# Edit .env with your values

# Pull the Ollama model
ollama pull qwen3:8b

# Run Renine
uv run python -m renine
```

## Development

```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=renine --cov-report=term-missing

# Lint
uv run ruff check renine/

# Format
uv run black renine/

# Type check
uv run mypy renine/
```

## Architecture

See `docs/architecture_summary.txt` for the full architecture documentation.

## License

MIT
