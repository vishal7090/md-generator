# Examples — CLI / extras pairing

```bash
pip install "mdengine[pdf]"
md-pdf report.pdf out.md
```

```bash
pip install "mdengine[db,api]"
md-db --config ./db.yaml
```

```bash
pip install "mdengine[playwright]"
playwright install chromium
md-playwright --help
```

```bash
pip install "mdengine[url-full]"
md-url https://example.com/page ./web-out --artifact-layout
```
