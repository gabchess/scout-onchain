"""Small dependency-free secret scan for the local MVP."""

import re
import subprocess
import sys
from pathlib import Path

PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN .*PRIVATE KEY-----"),
    re.compile(
        r"(?:api[_ -]?key|password|mnemonic|seed phrase|private key)\s*[:=]\s*['\"][^'\"]+",
        re.I,
    ),
    re.compile(r"0x[a-f0-9]{64}", re.I),
    # GitHub personal access / fine-grained tokens.
    re.compile(r"\bghp_[A-Za-z0-9]{36,}\b"),
    re.compile(r"\bgh[oprs]_[A-Za-z0-9]{36,}\b"),
    # OpenAI / generic "sk-" secret keys and Stripe live secret keys.
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk_live_[A-Za-z0-9]{16,}\b"),
    # Slack bot/user tokens.
    re.compile(r"\bxox[bp]-[A-Za-z0-9-]{10,}\b"),
    # Google API keys.
    re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    # JWT-shaped tokens (three base64url segments).
    re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
    # Bare BIP-39 mnemonic: the entire line is nothing but 12 or 24
    # space-separated lowercase words, with no other content. Anchored to
    # the whole line (rather than any 12-word run) so ordinary prose in
    # docs/comments doesn't false-positive.
    re.compile(r"^\s*(?:[a-z]+ ){11}[a-z]+\s*$"),
    re.compile(r"^\s*(?:[a-z]+ ){23}[a-z]+\s*$"),
]
EXCLUDED = {".git", ".venv", "__pycache__", ".pytest_cache", ".claude"}


def _is_dotenv(path: Path) -> bool:
    return path.name == ".env" or (path.name.startswith(".env.") and path.name != ".env.example")


def dotenv_findings(root: Path) -> list[str]:
    """A committed .env is a finding. In a git checkout only tracked files count."""
    try:
        tracked = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            capture_output=True,
            check=True,
        ).stdout.decode()
        candidates = [root / name for name in tracked.split("\0") if name]
    except (OSError, subprocess.CalledProcessError):
        candidates = [p for p in root.rglob(".env*") if not any(x in EXCLUDED for x in p.parts)]
    return [f"{path}: committed .env file" for path in candidates if _is_dotenv(path)]


def scan(root: Path) -> list[str]:
    findings: list[str] = dotenv_findings(root)
    scanner_path = Path(__file__).resolve()
    for path in root.rglob("*"):
        if (
            not path.is_file()
            or path.resolve() == scanner_path
            or any(part in EXCLUDED for part in path.parts)
        ):
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            if any(pattern.search(line) for pattern in PATTERNS):
                findings.append(f"{path}:{line_no}")
    return findings


if __name__ == "__main__":
    findings = scan(Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd())
    if findings:
        print("\n".join(findings))
        raise SystemExit(1)
    print("no credential-shaped secrets found")
