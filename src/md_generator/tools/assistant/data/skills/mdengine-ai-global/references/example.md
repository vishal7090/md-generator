# Examples — global

## Minimal environment

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Unix: source .venv/bin/activate
pip install -U pip
pip install "mdengine[pdf,word]"
python -c "import md_generator; print('md_generator OK')"
```

## Two CLIs

```bash
md-pdf manual.pdf ./out/doc.md
md-word notes.docx ./out/notes.md
```

Use `md-<tool> --help` for flags.
