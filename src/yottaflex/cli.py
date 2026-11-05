from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from . import __version__
from .generator import DEFAULT_SEED, export
from .server import serve


def main() -> None:
    parser = argparse.ArgumentParser(prog="yottaflex", description="Generate and review synthetic supportive retention signals.")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="Generate CSV, JSONL, SQLite and supporting validation artifacts.")
    gen.add_argument("--size", choices=["starter", "full"], default="starter")
    gen.add_argument("--count", type=int, help="Override employee count (min 1, max 10000).")
    gen.add_argument("--seed", type=int, default=DEFAULT_SEED)
    gen.add_argument("--output", type=Path, default=Path("data/generated"))
    val = sub.add_parser("validate", help="Read the validation report from a generated dataset.")
    val.add_argument("--input", type=Path, default=Path("data/generated"))
    rep = sub.add_parser("repro-check", help="Regenerate twice and compare all output checksums.")
    rep.add_argument("--size", choices=["starter", "full"], default="starter")
    rep.add_argument("--count", type=int, help="Override employee count.")
    rep.add_argument("--seed", type=int, default=DEFAULT_SEED)
    web = sub.add_parser("serve", help="Start the local review dashboard.")
    web.add_argument("--input", type=Path, default=Path("data/generated"))
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.command == "generate":
        count = args.count if args.count is not None else (10000 if args.size == "full" else 250)
        if not 1 <= count <= 10000: parser.error("--count must be between 1 and 10000")
        result = export(args.output, count, args.seed)
        print(json.dumps({"output": str(args.output.resolve()), "employees": count, "validation_passed": result["validation"]["passed"], "attrition_rate": result["validation"]["attrition_rate"]}, indent=2))
        if not result["validation"]["passed"]:
            raise SystemExit(1)
    elif args.command == "validate":
        report = json.loads((args.input / "validation_summary.json").read_text(encoding="utf-8"))
        print(json.dumps(report, indent=2))
        if not report["passed"]: raise SystemExit(1)
    elif args.command == "repro-check":
        count = args.count if args.count is not None else (10000 if args.size == "full" else 250)
        scratch_root = Path("work")
        scratch_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="yottaflex-repro-", dir=scratch_root) as tmp:
            root = Path(tmp)
            a, b = root / "a", root / "b"
            export(a, count, args.seed); export(b, count, args.seed)
            ca = (a / "checksums.sha256").read_text(encoding="utf-8")
            cb = (b / "checksums.sha256").read_text(encoding="utf-8")
            identical = ca == cb
            print(json.dumps({"employees": count, "seed": args.seed, "all_artifact_checksums_match": identical}, indent=2))
            if not identical: raise SystemExit(1)
    elif args.command == "serve":
        serve(args.input, args.host, args.port)


if __name__ == "__main__":
    main()
