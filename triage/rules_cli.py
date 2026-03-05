from __future__ import annotations

import argparse
from typing import Sequence

from .rules_engine import load_knowledge_base


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m triage.rules_cli", description="规则文件工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="校验规则文件")
    validate_parser.add_argument("--rules", required=True, help="规则文件路径（JSON/YAML）")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate":
        try:
            kb = load_knowledge_base(args.rules)
            print(
                f"[OK] 校验通过: file={args.rules}, version={kb.version}, "
                f"engine_mode={kb.engine_mode}, profiles={','.join(kb.profile_ids) or 'N/A'}"
            )
            return 0
        except Exception as exc:
            print(f"[ERROR] 校验失败: {exc}")
            return 1

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
