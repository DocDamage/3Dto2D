from __future__ import annotations

import argparse
import json
from pathlib import Path

from services.trust_service import SupplyChainService


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requirements", required=True)
    parser.add_argument("--sbom", required=True)
    parser.add_argument("--provenance", required=True)
    parser.add_argument("--source-revision", default="unknown")
    parser.add_argument("--builder-id", default="local")
    parser.add_argument("artifacts", nargs="+")
    args = parser.parse_args()
    SupplyChainService.generate_sbom(Path(args.requirements), Path(args.sbom))
    result = SupplyChainService.build_provenance([Path(item) for item in args.artifacts], source_revision=args.source_revision, builder_id=args.builder_id, invocation={"artifacts": [Path(item).name for item in args.artifacts]}, output=Path(args.provenance))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
