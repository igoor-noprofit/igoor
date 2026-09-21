"""Pre-submission sensitivity audit for the MSIX package.

Encodes the manual Sep-2026 audit: scans the packaging layout (and optionally
the built .msix archive) for anything that must never ship - tokens, API
keys, certs/private keys, databases/logs, dev .env, dev-username leakage.

  python tools/audit_package.py                       # audit installer/msix/layout
  python tools/audit_package.py --msix IGOOR-x.y.z.w.msix   # also list archive entries

Exit code 0 = clean, 1 = findings. Run before every Store submission
(docs/updates.md release checklist).
"""
import argparse
import getpass
import json
import re
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LAYOUT = REPO / "installer" / "msix" / "layout"
ENV_PRODUCTION = REPO / "installer" / "msix" / "env.production"

FAILURES = []


def fail(msg):
    FAILURES.append(msg)
    print(f"FAIL  {msg}")


def ok(msg):
    print(f"PASS  {msg}")


def info(msg):
    print(f"INFO  {msg}")


# Filenames that must not appear inside the package. cacert.pem under
# botocore/certifi is a public CA bundle and explicitly allowed.
FORBIDDEN_NAMES = ("github_token", ".pfx", ".pfx\"", ".cer", ".key")
ALLOWED_PEM = ("botocore/cacert.pem", "certifi/cacert.pem")

TOKEN_PATTERNS = ("ghp_", "gho_", "gsk_", "sk-ant-", "sk-proj-", "xai-")
PLACEHOLDER_USERS = {"yourusername", "<user_name>", "username", "public", "default", "all users"}


def forbidden_name_check(rel_path: str):
    low = rel_path.lower()
    if "github_token" in low:
        return "token file in package"
    for ext in (".pfx", ".cer", ".key"):
        if low.endswith(ext):
            return f"cert/key file in package ({ext})"
    if low.endswith(".pem") and not any(p in low for p in ALLOWED_PEM):
        return "unexpected .pem in package"
    if low.endswith((".db", ".sqlite", ".sqlite3", ".log", ".bak")):
        return "database/log/backup file in package"
    if low.endswith(".env") and low != "_internal/.env":
        return "unexpected .env file in package"
    return None


def scan_layout(layout: Path):
    if not layout.is_dir():
        fail(f"layout not found: {layout}")
        return

    env_file = layout / "_internal" / ".env"
    if not env_file.is_file():
        fail("layout/_internal/.env missing")
    elif ENV_PRODUCTION.is_file():
        if env_file.read_text(encoding="utf-8").strip() == ENV_PRODUCTION.read_text(encoding="utf-8").strip():
            ok("shipped .env matches env.production")
        else:
            fail("shipped .env DIFFERS from env.production")

    username = (getpass.getuser() or "").lower()
    users_re = re.compile(r"[Cc]:[\\/]Users[\\/]?([^\s\\/:\"'<>|]+)")
    files = [p for p in layout.rglob("*") if p.is_file()]
    text_scanned = 0
    for p in files:
        rel = p.relative_to(layout).as_posix()
        reason = forbidden_name_check(rel)
        if reason:
            fail(f"{reason}: {rel}")
        try:
            blob = p.read_bytes()
        except OSError:
            continue
        if b"\x00" in blob[:4096]:
            continue  # binary - skip content scan
        try:
            text = blob.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            continue
        text_scanned += 1
        for tok in TOKEN_PATTERNS:
            if tok in text:
                fail(f"token-shaped string '{tok}' in {rel}")
        for m in users_re.finditer(text):
            who = m.group(1).lower()
            if username and who == username:
                fail(f"dev username in path leak: {rel} ('{m.group(0)}')")
    ok(f"scanned {len(files)} files ({text_scanned} text) for secrets/path leaks")

    for settings in layout.glob("_internal/plugins/*/settings.json"):
        try:
            data = json.loads(settings.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            fail(f"unreadable plugin settings: {settings.relative_to(layout)}")
            continue
        for k, v in data.items():
            if "api_key" in k.lower() and v:
                fail(f"non-empty api key default in {settings.relative_to(layout)}:{k}")
    for defaults in layout.glob("_internal/locales/*/default_settings.json"):
        data = json.loads(defaults.read_text(encoding="utf-8"))
        ai = data.get("plugins", {}).get("onboarding", {}).get("ai", {})
        if ai.get("api_key"):
            fail(f"non-empty api key in {defaults.relative_to(layout)}")
    ok("bundled plugin/locale settings contain no API keys")


def scan_msix(msix: Path):
    if not msix.is_file():
        fail(f"msix not found: {msix}")
        return
    with zipfile.ZipFile(msix) as z:
        names = z.namelist()
    bad = []
    for n in names:
        rel = n.lstrip("/").removeprefix("layout/")
        reason = forbidden_name_check(rel)
        if reason:
            bad.append(f"{reason}: {rel}")
    for b in bad:
        fail(b)
    ok(f"archive listing: {len(names)} entries, {len(bad)} forbidden names")
    envs = [n for n in names if n.endswith(".env")]
    if envs == ["_internal/.env"] or envs == ["layout/_internal/.env"]:
        ok("archive contains exactly one .env (_internal/.env)")
    elif envs:
        fail(f"unexpected .env entries in archive: {envs}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--layout", default=str(LAYOUT), help="packaging layout dir (default: installer/msix/layout)")
    ap.add_argument("--msix", help="also audit this built .msix archive's entry list")
    args = ap.parse_args()

    scan_layout(Path(args.layout))
    if args.msix:
        scan_msix(Path(args.msix))

    if FAILURES:
        print(f"\n{len(FAILURES)} finding(s) - DO NOT SUBMIT")
        return 1
    print("\nAudit clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
