"""Local fail-closed scope gate. No GitHub Actions required.

Usage: python scripts/check_scope.py [base-ref] [head-ref]
Defaults to the contract's immutable base and HEAD.
"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "scope" / "active.json"

def changed_files(base, head):
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACDMRTUXB", base, head],
        cwd=ROOT, check=True, text=True, capture_output=True
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]

def validate(paths, contract):
    permitted = set(contract["allowed_files"])
    forbidden = tuple(contract["forbidden_paths"])
    failures = []
    for path in paths:
        if path not in permitted or any(path.startswith(x) for x in forbidden):
            failures.append(path)
    if not contract.get("base_ref") or not contract.get("feature_ref"):
        failures.append("<missing-contract-identifiers>")
    return failures

def main():
    try:
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        base = sys.argv[1] if len(sys.argv) > 1 else contract["base_ref"]
        head = sys.argv[2] if len(sys.argv) > 2 else "HEAD"
        paths = changed_files(base, head)
        failures = validate(paths, contract)
        if failures:
            print("BLOCKED — changes outside the closed scope:\n" + "\n".join(failures))
            return 1
        print(f"PASS — {len(paths)} changed files, all within Block 4.1 allowlist")
        return 0
    except Exception as exc:
        print(f"BLOCKED — unable to validate scope: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
