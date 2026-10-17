#!/usr/bin/env python3
"""Fail-closed scope gate. Run: python tools/scope_gate.py --base-ref origin/main"""
import argparse
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROTECTED = {"GATE_001_SCOPE_LOCK.md", "tools/scope_gate.py", "scope/active.json"}
KINDS = {"development", "bugfix", "audit"}

def run_git(*args):
    result = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git failed")
    return result.stdout

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-ref", default="origin/main")
    args = parser.parse_args()
    failures = []
    contract_path = ROOT / "scope/active.json"
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("BLOCKED: missing/invalid scope/active.json:", exc)
        return 1
    for field in ("id", "kind", "objective", "allowed_paths", "allowed_changes", "forbidden_changes", "acceptance"):
        if not contract.get(field):
            failures.append(f"missing scope field: {field}")
    if contract.get("kind") not in KINDS:
        failures.append("kind must be development, bugfix or audit")
    paths = contract.get("allowed_paths", [])
    if not isinstance(paths, list) or not paths or any(not isinstance(p, str) or not p.strip() or "*" in p or "?" in p or p.startswith("/") or ".." in pathlib.PurePosixPath(p).parts for p in paths):
        failures.append("allowed_paths must be explicit safe paths without globs")
        paths = []
    try:
        # Includes tracked changes and untracked local files; deleted and renamed paths are checked.
        committed = run_git("diff", "--name-only", "--no-renames", f"{args.base_ref}...HEAD").splitlines()
        working = run_git("diff", "--name-only", "--no-renames", "HEAD").splitlines()
        untracked = run_git("ls-files", "--others", "--exclude-standard").splitlines()
        changed = sorted(set(committed + working + untracked))
    except RuntimeError as exc:
        print("BLOCKED: could not assess diff:", exc)
        return 1
    if not changed:
        failures.append("no changed files to validate")
    if contract.get("kind") == "audit" and changed:
        failures.append("audit is read-only; any changed files are forbidden")
    for file in changed:
        if file in PROTECTED:
            failures.append(f"protected gate/contract modified: {file}")
        if not any(file == p.rstrip("/") or file.startswith(p.rstrip("/") + "/") for p in paths):
            failures.append(f"out-of-scope path: {file}")
    if failures:
        print("SCOPE GATE BLOCKED")
        for failure in failures:
            print(" -", failure)
        return 1
    print("SCOPE GATE PATH CHECK PASSED")
    print("Scope:", contract["id"], "|", contract["kind"])
    print("Reviewed paths:", len(changed))
    print("NOTE: semantic diff review and explicit user approval remain mandatory.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
