"""Fail on credential files or common literal secrets; never print matched values."""

import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}\b"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{24,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\r\n]+[A-Za-z0-9+/=\r\n]{40,}"),
    re.compile(r'''(?i)(?:api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*["'][A-Za-z0-9_+/=-]{24,}["']'''),
]
FORBIDDEN_PARTS = {".aws", ".ssh", "secrets", "credentials", "node_modules", ".venv", ".tools", ".cache", "__pycache__", ".pytest_cache", "dist", "artifacts"}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def violations(name: str, data: bytes) -> list[str]:
    path = Path(name)
    problems = []
    if (set(path.parts) & FORBIDDEN_PARTS or
        (path.name.startswith(".env") and path.name != ".env.example") or
        path.suffix.lower() in {".pem", ".key", ".p12", ".pfx", ".db", ".log"} or
        path.name in {"credentials.json", "service-account.json", "id_rsa", "id_ed25519"}):
        problems.append("credential/runtime file must not be tracked")
    source = data.decode("utf-8", errors="replace")
    if any(pattern.search(source) for pattern in PATTERNS):
        problems.append("possible literal secret; review locally (value withheld)")
    return problems


def self_test():
    token = ("gh" + "p_") + "A" * 36
    assert violations("app.py", token.encode())
    assert violations(".env", b"SETTING=value")
    assert violations("frontend/node_modules/file.js", b"nothing")
    assert not violations(".env.example", b"FV_CLOUD_API_KEY=\n")
    assert not violations("app.py", b"password = 'test-password'\n")
    print("PASS: secret-check self-tests")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true", help="Inspect index contents before a commit")
    parser.add_argument("--history", action="store_true", help="Also inspect every reachable Git tree")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    if subprocess.run(["git", "check-ignore", "-q", ".env"], cwd=ROOT).returncode:
        raise SystemExit("FAIL: .env must be ignored")
    rows = []
    if args.staged:
        names = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").decode().split("\0")
        rows.extend((name, git("show", f":{name}")) for name in names if name)
    else:
        names = git("ls-files", "--cached", "--others", "--exclude-standard", "-z").decode().split("\0")
        rows.extend((name, (ROOT / name).read_bytes()) for name in names if name and (ROOT / name).is_file())
    if args.history:
        seen = set()
        for commit in git("rev-list", "--all").decode().splitlines():
            for entry in git("ls-tree", "-r", "-z", commit).decode().split("\0"):
                if not entry:
                    continue
                metadata, name = entry.split("\t", 1)
                oid = metadata.split()[2]
                if (oid, name) not in seen:
                    seen.add((oid, name))
                    rows.append((name, git("cat-file", "blob", oid)))
    failed = False
    for name, data in rows:
        for issue in violations(name, data):
            print(f"FAIL: {name}: {issue}")
            failed = True
    if failed:
        raise SystemExit(1)
    print(f"PASS: {len(rows)} source/index/history entries checked; no matching secrets or excluded files")


if __name__ == "__main__":
    main()
