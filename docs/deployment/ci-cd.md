# CI/CD

The existing CI workflow runs a Python matrix, installs selected extras, tests `db-to-md/tests`, and builds the distribution. Documentation deployment is handled by the dedicated docs workflows added with this site.

## Documentation Pipeline

- Install `.[docs]`.
- Run `mkdocs build --strict` to validate nav, links, and plugin configuration.
- Upload the generated site as a GitHub Pages artifact on main branch pushes.
- Build PR documentation artifacts for review.
