"""Clone or update remote Git repositories into a local cache for codeflow scans."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

_LOG = logging.getLogger(__name__)

_ENV_CACHE = "CODEFLOW_GIT_CACHE"


class GitLoaderError(RuntimeError):
    """Failed to run git or resolve a remote workspace."""


_GIT_HOST_HINTS = re.compile(
    r"(github\.com|gitlab\.com|bitbucket\.org|dev\.azure\.com|visualstudio\.com)(/|:|$)",
    re.I,
)


def is_git_remote(s: str) -> bool:
    """True if ``s`` looks like a Git remote URL (not a local filesystem path)."""
    t = (s or "").strip()
    if not t:
        return False
    tl = t.lower()
    if tl.startswith("git@"):
        return True
    if tl.startswith("ssh://"):
        return True
    if tl.endswith(".git"):
        return True
    if tl.startswith("http://") or tl.startswith("https://"):
        return bool(_GIT_HOST_HINTS.search(t))
    return False


def default_cache_root() -> Path:
    """User-level cache directory for cloned repositories."""
    if raw := os.environ.get(_ENV_CACHE, "").strip():
        return Path(raw).expanduser().resolve()
    return Path.home() / ".cache" / "codeflow" / "repos"


def cache_dir_for_url(url: str) -> Path:
    """Stable subdirectory under :func:`default_cache_root` for ``url``."""
    key = hashlib.sha256(url.strip().encode("utf-8")).hexdigest()
    return default_cache_root() / key


def _ensure_git_available() -> None:
    try:
        subprocess.run(
            ["git", "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        raise GitLoaderError("git is not available on PATH or did not respond.") from e


def _ssh_env(ssh_key_path: Path | None) -> dict[str, str]:
    env = os.environ.copy()
    if ssh_key_path is not None:
        p = ssh_key_path.expanduser().resolve()
        if not p.is_file():
            raise GitLoaderError(f"SSH key file not found: {p}")
        env["GIT_SSH_COMMAND"] = f'ssh -i "{p.as_posix()}" -o IdentitiesOnly=yes'
    return env


def _apply_https_auth_token(url: str, token: str) -> str:
    """Embed ``token`` into an HTTPS URL without logging it. Host-specific conventions."""
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https"):
        return url
    host = (parts.hostname or "").lower()
    tok_q = quote(token, safe="")
    if "github.com" in host:
        userinfo = f"x-access-token:{tok_q}"
    elif "gitlab.com" in host or host.endswith(".gitlab.com"):
        userinfo = f"oauth2:{tok_q}"
    elif "bitbucket.org" in host:
        userinfo = f"x-token-auth:{tok_q}"
    elif "dev.azure.com" in host or "visualstudio.com" in host:
        # Azure DevOps PAT as HTTP basic user (empty password)
        userinfo = tok_q
    else:
        userinfo = f"oauth2:{tok_q}"
    netloc = userinfo + "@" + (parts.hostname or "")
    if parts.port:
        netloc += f":{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _safe_url_for_log(url: str) -> str:
    """Strip secrets from URL for logging (HTTPS userinfo, no raw tokens)."""
    t = url.strip()
    if t.startswith("git@"):
        m = re.match(r"git@([^:]+):(.+)", t)
        if m:
            return f"ssh://{m.group(1)}/{m.group(2)}"
        return "ssh-git-remote"
    p = urlsplit(t)
    if not p.hostname:
        return "<invalid-url>"
    host = p.hostname + (f":{p.port}" if p.port else "")
    return f"{p.scheme}://{host}{p.path or ''}"


def _run_git(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 600,
) -> None:
    r = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()[:2000]
        raise GitLoaderError(f"git failed ({r.returncode}): {' '.join(args[:4])}… — {err}")


def clean_all_cache(cache_root: Path | None = None) -> None:
    """Remove the entire clone cache tree."""
    root = cache_root if cache_root is not None else default_cache_root()
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
        _LOG.info("Removed git cache directory %s", root)


def clone_or_update_repo(
    url: str,
    *,
    branch: str | None = None,
    commit: str | None = None,
    no_cache: bool = False,
    auth_token: str | None = None,
    ssh_key_path: Path | None = None,
) -> Path:
    """
    Return a resolved path to a local clone of ``url``.

    Clones live under :func:`default_cache_root` unless ``CODEFLOW_GIT_CACHE`` is set.
    Do not log ``auth_token`` or URLs containing credentials.
    """
    _ensure_git_available()
    raw_url = url.strip()
    clone_url = _apply_https_auth_token(raw_url, auth_token) if auth_token else raw_url
    env = _ssh_env(ssh_key_path)
    repo_path = cache_dir_for_url(raw_url)
    repo_path.parent.mkdir(parents=True, exist_ok=True)

    log_url = _safe_url_for_log(raw_url)
    _LOG.info("Git workspace target: %s (cache path %s)", log_url, repo_path)

    if no_cache and repo_path.exists():
        shutil.rmtree(repo_path, ignore_errors=True)
        _LOG.info("Removed existing cache (--no-git-cache)")

    if not repo_path.exists():
        clone_cmd = ["git", "clone", "--depth", "50"]
        if branch:
            clone_cmd.extend(["-b", branch])
        clone_cmd.extend([clone_url, str(repo_path)])
        _LOG.info("Cloning repository")
        _run_git(clone_cmd, env=env)
    else:
        _LOG.info("Updating cached repository")
        _run_git(["git", "-C", str(repo_path), "fetch", "--all"], env=env)
        try:
            _run_git(["git", "-C", str(repo_path), "pull", "--ff-only"], env=env)
        except GitLoaderError as e:
            _LOG.warning("git pull --ff-only failed; using cached state: %s", e)

    if commit and not branch:
        # Fresh shallow clone may not have arbitrary SHAs; deepen then checkout.
        _run_git(["git", "-C", str(repo_path), "fetch", "--depth", "500", "origin"], env=env)

    if branch:
        _LOG.info("Checking out branch %s", branch)
        _run_git(["git", "-C", str(repo_path), "checkout", branch], env=env)

    if commit:
        _LOG.info("Checking out commit %s", commit[:12])
        try:
            _run_git(["git", "-C", str(repo_path), "fetch", "origin", commit, "--depth", "100"], env=env)
        except GitLoaderError:
            _LOG.debug("fetch depth for commit failed, trying checkout anyway")
        _run_git(["git", "-C", str(repo_path), "checkout", commit], env=env)

    return repo_path.resolve()
