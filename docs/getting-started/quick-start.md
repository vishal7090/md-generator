# Quick Start

## Local Editable Install

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e ".[pdf,word,api]"
```

## Run A Converter

```bash
md-pdf report.pdf report.md
md-word notes.docx notes.md
md-url https://example.com ./page-out --artifact-layout
```

## Run The Documentation Site

```bash
pip install -e ".[docs]"
mkdocs serve
```

Open `http://127.0.0.1:8000/`.
