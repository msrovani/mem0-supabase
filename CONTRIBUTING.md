# Contributing to Mem0-Supabase

Thank you for your interest in contributing! This guide will help you get started.

## Development Setup

```bash
# 1. Fork and clone
git clone https://github.com/YOUR_USERNAME/mem0-supabase.git
cd mem0-supabase

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# 3. Install dependencies
pip install -e ".[test,dev]"

# 4. Copy env file
cp .env.example .env
# Edit .env with your credentials

# 5. Run tests
pytest tests/ -v
```

## Code Style

We use **ruff** for linting and formatting:

```bash
# Format code
ruff format mem0/ server/ tests/

# Check for issues
ruff check mem0/ server/ tests/

# Type check
mypy mem0/ --ignore-missing-imports
```

## Pull Request Process

1. **Create a feature branch**: `git checkout -b feat/your-feature`
2. **Write tests**: Add tests for new functionality
3. **Follow conventions**: Use conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`)
4. **Update docs**: Update README and CHANGELOG if applicable
5. **Ensure CI passes**: All tests and linting must pass
6. **Request review**: Tag a maintainer

## Commit Convention

```
type(scope): description

feat(api): add bulk create endpoint
fix(core): resolve metadata=None crash
docs(readme): update installation instructions
refactor(cache): optimize LRU eviction
test(core): add layer-by-layer tests
```

## Testing

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_layer_by_layer.py -v

# With coverage
pytest tests/ --cov=mem0 --cov-report=html
```

## Architecture

See [AI_CONTEXT.md](AI_CONTEXT.md) for the full architecture overview.

## Reporting Issues

- **Bug**: Include reproduction steps, expected vs actual behavior
- **Feature request**: Describe the use case and desired outcome
- **Security**: See [SECURITY.md](SECURITY.md) for responsible disclosure

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
