# Local Development

## Editable Development Environment

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
pip install -e ".[dev,all,docs]"
```

## Test Commands

Run the full configured test discovery:

```bash
python -m pytest
```

Run the CI-aligned subset currently used by the existing workflow:

```bash
python -m pytest db-to-md/tests -v -m "not integration"
```

## Package Build

```bash
python -m pip install build
python -m build
```
