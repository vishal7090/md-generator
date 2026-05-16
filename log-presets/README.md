# User log parser presets

Drop `*.yaml` files here (or under `~/.mdengine/log/presets/`) and reference them with:

```bash
md-log --preset myformat --input app.log --output ./out
```

## Example: `myformat.yaml`

```yaml
parser:
  preset: myformat
  line_regex: "^(?P<timestamp>\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2})\\s+\\[(?P<level>\\w+)\\]\\s+(?P<message>.*)$"
```

Named groups: `timestamp`, `level`, `message` (optional: `thread`, `logger`).

## Environment

Set `MD_LOG_PRESET_DIRS` to a path-separated list of extra preset directories.
