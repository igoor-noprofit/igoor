"""Layer-2 upgrade rehearsal: automated post-upgrade checks.

Run against a TEST APPDATA folder (second Windows account / VM) after
installing the new MSIX over the old one, per docs/updates.md:

  1. BEFORE the upgrade (old version still installed):
       python tools/upgrade_check.py --appdata <path> --save-baseline base.json
  2. AFTER the upgrade, with the new version booted once:
       python tools/upgrade_check.py --appdata <path> --baseline base.json \
               [--url http://127.0.0.1:9714]

Checks: settings.json intact, every plugin table present, row counts match
the baseline, pre-migration backups listed, no DB/migration ERROR lines in
today's log, and (with --url) the /health endpoint answers.

Exit code 0 = all green. Manual UI checklist still applies (see docs).
"""
import argparse
import json
import sqlite3
import sys
import urllib.request
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

RESULTS = []


def report(ok, label, detail=""):
    RESULTS.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {label}" + (f" - {detail}" if detail else ""))


def table_counts(db_file):
    conn = sqlite3.connect(db_file)
    try:
        names = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        return {n: conn.execute(f"SELECT COUNT(*) FROM {n}").fetchone()[0] for n in names}
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--appdata", required=True, help="APPDATA root containing the igoor folder")
    ap.add_argument("--baseline", help="baseline JSON saved before the upgrade")
    ap.add_argument("--save-baseline", dest="save_baseline", help="write row counts to this file and exit")
    ap.add_argument("--url", help="also check this base URL's /health endpoint")
    args = ap.parse_args()

    root = Path(args.appdata)
    appdata = root / "igoor"
    db_file = appdata / "database" / "igoor.db"

    settings_file = appdata / "settings.json"
    ok = settings_file.is_file()
    report(ok, "settings.json exists", str(settings_file))
    user_settings = {}
    if ok:
        try:
            user_settings = json.loads(settings_file.read_text(encoding="utf-8"))
            report(True, "settings.json parses")
        except json.JSONDecodeError as e:
            report(False, "settings.json parses", str(e))

    if ok and user_settings:
        ai = user_settings.get("plugins", {}).get("onboarding", {}).get("ai", {})
        report(bool(ai.get("api_key")), "onboarding api_key still set (user value survived)")
        report("last_run_version" in user_settings, "last_run_version marker written")

    if not db_file.is_file():
        report(False, "igoor.db exists", str(db_file))
    else:
        try:
            counts = table_counts(db_file)
            report(len(counts) > 0, "plugin tables present", f"{len(counts)} tables")
            if args.save_baseline:
                Path(args.save_baseline).write_text(json.dumps(counts, indent=2), encoding="utf-8")
                print(f"Baseline saved to {args.save_baseline} ({len(counts)} tables)")
                return 0
            if args.baseline:
                base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
                for table, count in base.items():
                    if table not in counts:
                        report(False, f"table {table} survived", "MISSING")
                    else:
                        report(
                            counts[table] == count,
                            f"table {table} row count",
                            f"{counts[table]} (baseline {count})",
                        )
            backups = sorted((db_file.parent / "backups").glob("igoor_pre_*.db"))
            print(f"INFO  pre-migration backups: {len(backups)}"
                  + (f" (latest: {backups[-1].name})" if backups else ""))
        except sqlite3.Error as e:
            report(False, "igoor.db readable", str(e))

    log_file = appdata / "logs" / f"igoor_{date.today().strftime('%Y%m%d')}.log"
    if log_file.is_file():
        bad, migration = [], []
        for line in log_file.read_text(encoding="utf-8", errors="replace").splitlines():
            if " - ERROR - " not in line:
                continue
            if any(k in line for k in ("db_manager", "migration", "Schema sync", "sqlite3")):
                migration.append(line)
            else:
                bad.append(line)
        report(not migration, "no DB/migration errors in today's log",
               migration[0] if migration else "")
        if bad:
            print(f"WARN  {len(bad)} unrelated ERROR line(s) in today's log (review manually)")
    else:
        print(f"WARN  today's log not found: {log_file}")

    if args.url:
        try:
            with urllib.request.urlopen(f"{args.url.rstrip('/')}/health", timeout=5) as r:
                body = json.loads(r.read().decode("utf-8"))
            report(r.status == 200 and body.get("status") == "ok", "/health endpoint", str(body))
        except Exception as e:  # noqa: BLE001 - any transport failure is a failed check
            report(False, "/health endpoint", repr(e))

    failed = RESULTS.count(False)
    print(f"\n{len(RESULTS) - failed}/{len(RESULTS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
