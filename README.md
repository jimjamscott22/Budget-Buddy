# Personal Budget Tracker

A local desktop expense and monthly category budget tracker built with PySide6, SQLite, and Matplotlib.

## Run

Use Python 3.12 or newer with the project dependencies installed:

```powershell
python -m pip install -e ".[dev]"
python -m budget_tracker
```

```bash
uv run python -m budget_tracker
```

In this Codex workspace, the bundled Python runtime already has the dependencies installed:

```powershell
& 'C:\Users\Jamie\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m budget_tracker
```

The app stores its local database at `data/budget_tracker.db`.

## Test

```powershell
python -m pytest
```

