"""Layer-1 migration tests for the Store update safety net.

Builds synthetic "old" APPDATA folders in a temp dir (never touches the real
one), creates igoor.db from the schemas frozen in tools/fixtures/
db_tables_last_release.json (one release behind by construction), then runs
the CURRENT repo schemas through DatabaseManager.register_plugin and asserts:

  1. fresh install        - all tables created, no migration backup
  2. column addition      - new column added, old rows intact, default
                            backfilled, pre-migration backup taken
  3. drift self-heal      - plugin_metadata claims a version the table lacks
                            (the historical bug) - column added anyway
  4. honest failure       - impossible ALTER (NOT NULL without default) leaves
                            the recorded version untouched for retry next boot
  5. idempotent re-boot   - second registration adds nothing, no extra backups
  6. settings merge       - merge_missing semantics + SettingsManager top-level
                            default merge (user values never overwritten)

Run:  python tools/test_migrations.py   (exit code 0 = all green)
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
os.chdir(REPO)

# Point APPDATA at a temp root BEFORE the igoor modules resolve any path.
_TMP_ROOT = Path(tempfile.mkdtemp(prefix="igoor_migration_test_"))
os.environ["APPDATA"] = str(_TMP_ROOT)
os.environ["IGOOR_START_LANG"] = "en_EN"  # deterministic default_settings.json

import db_manager as db_mod
import settings_manager as sm_mod
from utils import merge_missing

FIXTURES = json.loads(
    (REPO / "tools" / "fixtures" / "db_tables_last_release.json").read_text(encoding="utf-8")
)


def current_db_tables():
    tables = {}
    for pj in sorted((REPO / "plugins").glob("*/plugin.json")):
        cfg = json.loads(pj.read_text(encoding="utf-8"))
        if cfg.get("requires_db"):
            tables[pj.parent.name] = cfg.get("db_tables", {})
    return tables


def prefixed(schema, table, plugin):
    """Same prefixing DatabaseManager applies to declared schemas."""
    s = schema.replace(
        f"CREATE TABLE IF NOT EXISTS {table}", f"CREATE TABLE IF NOT EXISTS {plugin}_{table}"
    )
    for other in FIXTURES.get(plugin, {}):
        if not other.startswith("__"):
            s = s.replace(f"REFERENCES {other}", f"REFERENCES {plugin}_{other}")
    return s


def db_path(appdata_root):
    return Path(appdata_root) / "igoor" / "database" / "igoor.db"


def backups(appdata_root):
    d = db_path(appdata_root).parent / "backups"
    return sorted(d.glob("igoor_pre_*.db")) if d.exists() else []


def colnames(conn, table):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def reset_singletons():
    if db_mod.DatabaseManager._instance is not None:
        db_mod.DatabaseManager._instance.close_all_connections()
    db_mod.DatabaseManager._instance = None
    sm_mod.SettingsManager._instance = None


def fresh_appdata(name):
    """Isolated APPDATA for one scenario, with singletons reset."""
    reset_singletons()
    root = Path(tempfile.mkdtemp(prefix=f"igoor_test_{name}_", dir=str(_TMP_ROOT)))
    os.environ["APPDATA"] = str(root)
    return root


def register_all(dm, tables_map):
    for plugin, tables in tables_map.items():
        dm.register_plugin(plugin, tables)


# ---------------------------------------------------------------- scenarios

def scenario_fresh_install():
    root = fresh_appdata("fresh")
    dm = db_mod.DatabaseManager()
    register_all(dm, current_db_tables())

    conn = sqlite3.connect(db_path(root))
    for plugin, tables in current_db_tables().items():
        for table in tables:
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (f"{plugin}_{table}",),
            )
            assert cur.fetchone(), f"missing table {plugin}_{table}"
    conn.close()
    assert not backups(root), "fresh install must not create migration backups"


def scenario_column_addition_and_backfill():
    root = fresh_appdata("upgrade")
    # Old database: last-release schemas, minus rag_documents.always_send
    # (simulates the version that predates that column).
    db_path(root).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path(root))
    for plugin, tables in FIXTURES.items():
        if plugin.startswith("__"):
            continue
        for table, cfg in tables.items():
            schema = prefixed(cfg["schema"], table, plugin)
            if plugin == "rag" and table == "documents":
                schema = schema.replace(", always_send INTEGER DEFAULT 0", "")
            conn.execute(schema)
    conn.execute(
        "INSERT INTO rag_documents (title, filename, created_at) "
        "VALUES ('Doc one', 'doc1.pdf', '2026-01-01')"
    )
    conn.commit()
    conn.close()

    # "Install the new version": register current schemas.
    dm = db_mod.DatabaseManager()
    register_all(dm, current_db_tables())

    conn = sqlite3.connect(db_path(root))
    cols = colnames(conn, "rag_documents")
    assert "always_send" in cols, f"always_send not added: {cols}"
    row = conn.execute("SELECT title, filename, always_send FROM rag_documents").fetchone()
    assert row == ("Doc one", "doc1.pdf", 0), f"old row broken or default not backfilled: {row}"
    conn.close()
    assert len(backups(root)) == 1, "expected exactly one pre-migration backup"


def scenario_drift_self_heal():
    root = fresh_appdata("drift")
    # conversation_threads at v1.1 (no speakers_id / speaker_id_method) while
    # plugin_metadata already claims v1.2 - the drift the old code produced by
    # recording versions that CREATE TABLE IF NOT EXISTS never applied.
    db_path(root).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path(root))
    old_threads = prefixed(
        FIXTURES["conversation"]["threads"]["schema"], "threads", "conversation"
    ).replace(", speakers_id INTEGER, speaker_id_method INTEGER", "")
    conn.execute(old_threads)
    conn.execute(
        "INSERT INTO conversation_threads (start_time, cause, topic, content) "
        "VALUES ('2026-01-01', 'idle', 'drift test', 'hello')"
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS plugin_metadata (
               plugin_name TEXT PRIMARY KEY, tables TEXT, version TEXT,
               last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""
    )
    current = current_db_tables()["conversation"]
    claims = {t: {"version": cfg["version"]} for t, cfg in current.items()}
    conn.execute(
        "INSERT OR REPLACE INTO plugin_metadata (plugin_name, tables, version) VALUES (?, ?, ?)",
        ("conversation", json.dumps(claims), "1.0"),
    )
    conn.commit()
    conn.close()

    dm = db_mod.DatabaseManager()
    register_all(dm, current_db_tables())

    conn = sqlite3.connect(db_path(root))
    cols = colnames(conn, "conversation_threads")
    assert "speakers_id" in cols and "speaker_id_method" in cols, f"drift not healed: {cols}"
    row = conn.execute("SELECT topic, speakers_id FROM conversation_threads").fetchone()
    assert row == ("drift test", None), f"old row broken after self-heal: {row}"
    conn.close()
    assert len(backups(root)) == 1


def scenario_honest_failure():
    root = fresh_appdata("failure")
    db_path(root).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path(root))
    conn.execute("CREATE TABLE IF NOT EXISTS synth_t (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO synth_t (name) VALUES ('keep me')")
    conn.commit()
    conn.close()

    new_cfg = {
        "t": {
            # req TEXT NOT NULL without default cannot be added via ALTER:
            # sync must fail loudly and NOT record version 2.0.
            "schema": "CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY, name TEXT, req TEXT NOT NULL)",
            "version": "2.0",
        }
    }
    dm = db_mod.DatabaseManager()
    dm.register_plugin("synth", new_cfg)

    conn = sqlite3.connect(db_path(root))
    assert "req" not in colnames(conn, "synth_t"), "impossible column must not appear"
    row = conn.execute("SELECT name FROM synth_t").fetchone()
    assert row == ("keep me",), "failed migration must not damage data"
    meta = conn.execute(
        "SELECT tables FROM plugin_metadata WHERE plugin_name = 'synth'"
    ).fetchone()
    recorded = json.loads(meta[0]) if meta and meta[0] else {}
    assert recorded.get("t", {}).get("version") != "2.0", (
        f"version recorded despite failed sync: {recorded}"
    )
    conn.close()


def scenario_idempotent_second_boot():
    root = fresh_appdata("idem")
    dm = db_mod.DatabaseManager()
    register_all(dm, current_db_tables())
    conn = sqlite3.connect(db_path(root))
    before = {
        f"{p}_{t}": colnames(conn, f"{p}_{t}")
        for p, tables in current_db_tables().items()
        for t in tables
    }
    conn.close()

    # Simulate a second boot: fresh process state, same APPDATA.
    reset_singletons()
    dm2 = db_mod.DatabaseManager()
    register_all(dm2, current_db_tables())

    conn = sqlite3.connect(db_path(root))
    after = {
        f"{p}_{t}": colnames(conn, f"{p}_{t}")
        for p, tables in current_db_tables().items()
        for t in tables
    }
    conn.close()
    assert before == after, "second boot changed the schema"
    assert not backups(root), "no ALTER must mean no new backup"


def scenario_merge_missing_unit():
    user = {"a": 1, "nested": {"x": "user", "keep": [1, 2]}, "lst": [1]}
    defaults = {
        "a": 99,
        "b": 2,
        "nested": {"x": "def", "y": "new"},
        "lst": [1, 2, 3],
        "new": {"k": "v"},
    }
    merged, added = merge_missing(user, defaults)
    assert merged["a"] == 1, "user scalar overwritten"
    assert merged["nested"] == {"x": "user", "keep": [1, 2], "y": "new"}, "nested merge wrong"
    assert merged["lst"] == [1], "user list touched"
    assert merged["new"] == {"k": "v"}
    assert added == 3, f"wrong added count: {added}"
    assert user["nested"] == {"x": "user", "keep": [1, 2]}, "input dict mutated"


def scenario_settings_top_level_merge():
    root = fresh_appdata("settings")
    appdata = root / "igoor"
    appdata.mkdir(parents=True)
    user_settings = {
        "plugins": {
            "onboarding": {
                "ai": {"api_key": "SECRET", "model_name": "user-model"},
                "prefs": {"lang": "fr_FR"},
            }
        },
        "plugins_activation": {"conversation": True},
    }
    (appdata / "settings.json").write_text(json.dumps(user_settings), encoding="utf-8")

    sm = sm_mod.SettingsManager()
    s = sm.get_settings()

    ai = s["plugins"]["onboarding"]["ai"]
    assert ai["api_key"] == "SECRET", "user API key overwritten"
    assert ai["model_name"] == "user-model", "user model overwritten"
    assert "temperature" in ai, "new default key not merged into ai"
    assert "reasoning_effort" in ai, "new default key not merged into ai"
    assert s["plugins"]["onboarding"]["prefs"]["lang"] == "fr_FR", "user lang overwritten"
    # Activation: user-set entries must never change; default entries for
    # plugins the old file did not know are ADDED (same as is_active does).
    assert s["plugins_activation"]["conversation"] is True, "activation entry changed"
    assert len(s["plugins_activation"]) > 1, "default activation entries not merged"

    # Merged keys must be persisted to disk too.
    on_disk = json.loads((appdata / "settings.json").read_text(encoding="utf-8"))
    assert on_disk["plugins"]["onboarding"]["ai"]["api_key"] == "SECRET"
    assert "temperature" in on_disk["plugins"]["onboarding"]["ai"]


# ------------------------------------------------------------------- runner

SCENARIOS = [
    scenario_fresh_install,
    scenario_column_addition_and_backfill,
    scenario_drift_self_heal,
    scenario_honest_failure,
    scenario_idempotent_second_boot,
    scenario_merge_missing_unit,
    scenario_settings_top_level_merge,
]


def main():
    failures = []
    for fn in SCENARIOS:
        name = fn.__name__
        try:
            fn()
            print(f"PASS  {name}")
        except AssertionError as e:
            failures.append((name, str(e)))
            print(f"FAIL  {name}: {e}")
        except Exception as e:  # noqa: BLE001 - a crash is a failure too
            failures.append((name, repr(e)))
            print(f"ERROR {name}: {e!r}")
    if not failures:
        shutil.rmtree(_TMP_ROOT, ignore_errors=True)
        print(f"\nAll {len(SCENARIOS)} scenarios green.")
        return 0
    print(f"\n{len(failures)} scenario(s) failed; temp dirs kept at {_TMP_ROOT}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
