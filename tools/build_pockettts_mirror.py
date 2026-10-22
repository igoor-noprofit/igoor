#!/usr/bin/env python3
"""Build a Google-Drive mirror folder for a pocket-tts language variant.

The pockettts plugin downloads its weights from public Google Drive folders
(see plugins/pockettts/models.csv) so users need no HuggingFace account.
The mirrors must mirror the GATED repo kyutai/pocket-tts (it includes the
voice-cloning weights), at the exact revision the pocket-tts library pins in
its bundled configs — this script reads that revision for you.

Usage (repo root, venv python, logged into HuggingFace: `uvx hf auth login`):
    python tools/build_pockettts_mirror.py french
    python tools/build_pockettts_mirror.py english_18m_2026-10 --out builds/mirrors

Then:
  1. upload <out>/<variant>/ to Google Drive as a FOLDER (not a zip),
  2. add a row `<variant>,<folder-url>` to plugins/pockettts/models.csv,
  3. add the pinned revision to THIRD_PARTY_LICENSES.md under
     "Pocket TTS — model weights" (mirrored-revision list).

A mirror folder contains exactly: model.safetensors, tokenizer.model,
embeddings/ (cleaned). Preset voice embeddings whose source recordings are
not AGPLv3-compatible are excluded here (same list as models.csv's header).
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

GATED_REPO = "kyutai/pocket-tts"
EXCLUDED_EMBEDDINGS = {"cosette.safetensors", "jean.safetensors", "rafael.safetensors"}


def pinned_revision(variant):
    """Return (repo_id, revision) the pocket-tts lib pins for `variant`'s
    weights, from its bundled config yaml."""
    import yaml
    from pocket_tts.utils.config import CONFIGS_DIR

    cfg_path = CONFIGS_DIR / f"{variant}.yaml"
    if not cfg_path.is_file():
        sys.exit(f"Unknown variant '{variant}': no {cfg_path.name} in the installed pocket_tts")
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    m = re.match(r"hf://([^/]+/[^/]+)/.+@([0-9a-f]+)", cfg.get("weights_path") or "")
    if not m:
        sys.exit(f"Cannot parse a pinned revision from weights_path: {cfg.get('weights_path')!r}")
    return m.group(1), m.group(2)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("variant", help="pocket-tts variant, e.g. french or english_18m_2026-10")
    ap.add_argument("--out", default="builds/mirrors", help="output directory (default: builds/mirrors)")
    args = ap.parse_args()

    repo, revision = pinned_revision(args.variant)
    print(f"Variant '{args.variant}' is pinned to {repo}@{revision}")

    try:
        from huggingface_hub import snapshot_download
        src_root = snapshot_download(
            repo_id=repo,
            revision=revision,
            allow_patterns=[f"languages/{args.variant}/**"],
        )
    except Exception as e:
        sys.exit(
            f"Download from {repo}@{revision} failed: {e}\n"
            "The repo is gated: accept the terms at https://huggingface.co/kyutai/pocket-tts "
            "then log in with: uvx hf auth login"
        )

    src = Path(src_root) / "languages" / args.variant
    dst = Path(args.out) / args.variant
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)

    for name in ("model.safetensors", "tokenizer.model"):
        f = src / name
        if not f.is_file():
            sys.exit(f"Missing {name} in {src} — aborting, no mirror written")
        shutil.copy2(f, dst / name)

    skipped = []
    emb_src = src / "embeddings"
    if emb_src.is_dir():
        (dst / "embeddings").mkdir()
        for f in sorted(emb_src.glob("*.safetensors")):
            if f.name in EXCLUDED_EMBEDDINGS:
                skipped.append(f.name)
                continue
            shutil.copy2(f, dst / "embeddings" / f.name)

    for sidecar in dst.rglob("*.metadata"):
        sidecar.unlink()

    def mb(p):
        return f"{p.stat().st_size / 1e6:.1f} MB"

    print(f"\nMirror ready: {dst}")
    for f in sorted(dst.rglob("*")):
        if f.is_file():
            print(f"  {f.relative_to(dst)}  ({mb(f)})")
    if skipped:
        print(f"  excluded embeddings (license): {', '.join(skipped)}")
    print(
        f"\nNext: upload {dst} to Google Drive as a folder, add the row\n"
        f"  {args.variant},<drive-folder-url>\n"
        f"to plugins/pockettts/models.csv, and record the pinned revision "
        f"{revision[:12]} in THIRD_PARTY_LICENSES.md."
    )


if __name__ == "__main__":
    main()
