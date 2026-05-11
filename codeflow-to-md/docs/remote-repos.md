# Scanning remote Git repositories

The `codeflow scan` command accepts a **local path**, a **`.zip`**, or a **Git remote URL** as the first argument.

## Supported URL shapes

- **HTTPS**: `https://github.com/org/repo.git`, `https://gitlab.com/org/repo`, `https://bitbucket.org/org/repo`, `https://dev.azure.com/org/project/_git/repo`
- **SSH**: `git@github.com:org/repo.git`, `ssh://git@host/path/repo.git`
- **Suffix**: URLs ending in `.git` are treated as Git remotes when the host matches known providers (see `ingestion/git_loader.py`).

Generic `https://` URLs that are **not** on a recognized Git host are **not** treated as remotes (to avoid mistaking arbitrary web pages for repos).

## Cache directory

Clones are stored under:

- **`%USERPROFILE%\.cache\codeflow\repos\`** on Windows (under your home directory’s `.cache` layout), or
- **`~/.cache/codeflow/repos/`** on Unix-like systems.

Override with environment variable **`CODEFLOW_GIT_CACHE`** (absolute path to a directory).

- **`--no-git-cache`**: delete the cached directory for this URL only, then clone again.
- **`--clean-git-cache`**: delete the **entire** cache tree (all repos), then exit without scanning. Does not require a `path` argument.

## Branch and commit

- **`--git-branch` / `--branch`**: check out a branch after clone/update (also passed to `git clone -b` on first clone).
- **`--git-commit` / `--commit`**: check out a SHA after the branch step (may require network fetch; shallow clones can fail for arbitrary old commits).

## Authentication

- **HTTPS token**: `--git-auth-token` injects credentials in a host-specific way (GitHub: `x-access-token`, GitLab: `oauth2`, Bitbucket: `x-token-auth`, Azure DevOps: PAT as HTTP user). Tokens are **never** printed by the tool; prefer CI secret env vars mapped into this flag.
- **Token in URL**: you can pass `https://user:token@host/...` directly; avoid logging that string.
- **SSH**: use `git@…` URLs and optionally **`--git-ssh-key path/to/key`** (sets `GIT_SSH_COMMAND` for the `git` subprocess only).

## Examples

```bash
python -m md_generator.codeflow.cli.main scan https://github.com/org/repo.git --output ./out
python -m md_generator.codeflow.cli.main scan https://github.com/org/repo.git --branch develop
python -m md_generator.codeflow.cli.main scan git@github.com:org/repo.git --git-ssh-key ~/.ssh/id_ed25519
python -m md_generator.codeflow.cli.main scan --clean-git-cache
```

## Requirements

`git` must be on `PATH`. Failures (auth, network, missing repo) surface as a non-zero exit code and a short message on stderr.
