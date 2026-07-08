from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from glob import glob
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], check: bool = True, capture: bool = False, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=ROOT,
        check=check,
        text=True,
        capture_output=capture,
        env=env,
    )


def git(*args: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    return run(["git", *args], check=check, capture=capture)


def in_git_repo() -> bool:
    probe = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=ROOT, text=True, capture_output=True)
    return probe.returncode == 0 and probe.stdout.strip().lower() == "true"


def ensure_git_repo() -> None:
    if not in_git_repo():
        git("init")


def current_branch() -> str:
    result = git("branch", "--show-current", capture=True)
    branch = result.stdout.strip()
    return branch or "main"


def ensure_branch(branch: str) -> None:
    current = subprocess.run(["git", "branch", "--show-current"], cwd=ROOT, text=True, capture_output=True).stdout.strip()
    if current == branch:
        return
    exists = subprocess.run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=ROOT).returncode == 0
    if exists:
        git("checkout", branch)
    else:
        git("checkout", "-b", branch)


def changed_files() -> list[str]:
    result = git("status", "--porcelain", capture=True)
    files: list[str] = []
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        files.append(line[3:].strip())
    return files


def stage_files(patterns: list[str], all_files: bool) -> None:
    if all_files:
        git("add", "-A")
        return
    if not patterns:
        files = changed_files()
        if not files:
            return
        raise SystemExit(
            "No include patterns provided and --all was not set.\n"
            "Changed files:\n- " + "\n- ".join(files) + "\n\n"
            "Re-run with --all or one or more --include patterns."
        )
    resolved: list[str] = []
    for pattern in patterns:
        matches = glob(str(ROOT / pattern), recursive=True)
        if matches:
            resolved.extend([str(Path(match).relative_to(ROOT)) for match in matches])
        else:
            resolved.append(pattern)
    git("add", "--", *resolved)


def has_staged_changes() -> bool:
    result = git("diff", "--cached", "--name-only", capture=True)
    return bool(result.stdout.strip())


def remote_exists(remote: str = "origin") -> bool:
    probe = subprocess.run(["git", "remote", "get-url", remote], cwd=ROOT, text=True, capture_output=True)
    return probe.returncode == 0 and bool(probe.stdout.strip())


def commit(message: str) -> None:
    name = subprocess.run(["git", "config", "--get", "user.name"], cwd=ROOT, text=True, capture_output=True).stdout.strip()
    email = subprocess.run(["git", "config", "--get", "user.email"], cwd=ROOT, text=True, capture_output=True).stdout.strip()
    if not name or not email:
        raise SystemExit(
            "Git identity is not configured. Run:\n"
            '  git config --global user.name "Your Name"\n'
            '  git config --global user.email "you@example.com"\n'
            "Then rerun the ship tool."
        )
    git("commit", "-m", message)


def push(remote: str, branch: str) -> None:
    git("push", "-u", remote, branch)


def deploy_with_vercel(prod: bool = True, yes: bool = True, token: str | None = None) -> None:
    if subprocess.run(["vercel", "--version"], cwd=ROOT, text=True, capture_output=True).returncode != 0:
        raise SystemExit("Vercel CLI is not installed. Install it with `npm i -g vercel`.")
    cmd = ["vercel"]
    if prod:
        cmd.append("--prod")
    if yes:
        cmd.append("--yes")
    env = os.environ.copy()
    if token:
        env["VERCEL_TOKEN"] = token
    run(cmd, env=env)


def is_streamlit_project() -> bool:
    return (ROOT / "app.py").exists() and any((ROOT / name).exists() for name in ["requirements.txt", "pyproject.toml"])


def start_streamlit_preview(port: int = 8501) -> None:
    env = os.environ.copy()
    env["STREAMLIT_SERVER_HEADLESS"] = "true"
    cmd = [sys.executable, "-m", "streamlit", "run", "app.py", "--server.port", str(port), "--server.headless", "true"]
    subprocess.Popen(cmd, cwd=ROOT, env=env)
    print(f"Started Streamlit preview on http://localhost:{port}")


def maybe_create_remote_with_gh(name: str, private: bool, remote: str = "origin") -> None:
    if remote_exists(remote):
        return
    if subprocess.run(["gh", "--version"], cwd=ROOT, text=True, capture_output=True).returncode != 0:
        raise SystemExit("No git remote found and GitHub CLI is unavailable.")
    auth = subprocess.run(["gh", "auth", "status"], cwd=ROOT, text=True, capture_output=True)
    if auth.returncode != 0:
        raise SystemExit("No git remote found and `gh` is not authenticated. Run `gh auth login` first.")
    visibility = "--private" if private else "--public"
    run(["gh", "repo", "create", name, visibility, "--source", ".", "--remote", remote, "--push"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Ship a buildathon project: stage, commit, push, and deploy.")
    parser.add_argument("--message", default="ship buildathon release", help="Commit message.")
    parser.add_argument("--branch", default="", help="Branch to push. Defaults to current branch or codex/ship-buildathon.")
    parser.add_argument("--remote", default="origin", help="Git remote name. Defaults to origin.")
    parser.add_argument("--all", action="store_true", help="Stage all tracked and untracked changes.")
    parser.add_argument("--include", action="append", default=[], help="Explicit file or glob to stage. Repeatable.")
    parser.add_argument("--init", action="store_true", help="Initialize a git repo if needed.")
    parser.add_argument("--create-remote", default="", help="Create a GitHub repo with gh if no remote exists.")
    parser.add_argument("--private", action="store_true", help="Create the GitHub repo as private when using --create-remote.")
    parser.add_argument("--deploy", action="store_true", help="Run deploy step after push.")
    parser.add_argument("--deploy-provider", choices=["auto", "vercel", "custom"], default="auto", help="Deployment provider.")
    parser.add_argument("--deploy-command", default="", help='Custom deploy command, e.g. "npm run deploy".')
    parser.add_argument("--dry-run", action="store_true", help="Print the intended actions without executing them.")
    args = parser.parse_args()

    if args.init:
        ensure_git_repo()
    elif not in_git_repo():
        raise SystemExit("This folder is not a git repository. Re-run with --init to create one.")

    branch = args.branch or current_branch()
    if branch in {"main", "master", ""} and not args.branch:
        branch = "codex/ship-buildathon"

    print(f"Repo: {ROOT}")
    print(f"Branch: {branch}")
    print(f"Remote: {args.remote}")
    print(f"Changes: {len(changed_files())}")

    if args.dry_run:
        print("Dry run only. No changes will be made.")
        return 0

    ensure_branch(branch)

    if args.create_remote:
        maybe_create_remote_with_gh(args.create_remote, args.private, remote=args.remote)

    stage_files(args.include, args.all)
    if not has_staged_changes():
        print("No staged changes detected. Nothing to commit.")
    else:
        commit(args.message)
        print(f"Committed: {args.message}")

    if remote_exists(args.remote):
        push(args.remote, branch)
        print(f"Pushed to {args.remote}/{branch}")
    else:
        print(f"No remote named '{args.remote}' found. Skipping push.")

    if args.deploy:
        provider = args.deploy_provider
        if provider == "auto":
            provider = "custom" if is_streamlit_project() else "vercel"

        if provider == "vercel":
            token = os.getenv("VERCEL_TOKEN", "").strip() or None
            deploy_with_vercel(prod=True, yes=True, token=token)
            print("Deployed with Vercel.")
        else:
            if args.deploy_command:
                run(shlex.split(args.deploy_command), env=os.environ.copy())
                print("Custom deploy command completed.")
            else:
                if is_streamlit_project():
                    start_streamlit_preview()
                else:
                    raise SystemExit("--deploy-provider custom requires --deploy-command unless this is a Streamlit project.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
