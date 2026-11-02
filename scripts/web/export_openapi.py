"""Export or check the versioned OpenAPI contract without starting the service."""

import argparse
import json
from pathlib import Path

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    import sys
    sys.path.insert(0, str(root))
    from services.simulator_api.app import create_app

    target = root / "contracts" / "web" / "v1" / "openapi.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    app = create_app(start_worker=False)
    content = json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    app.state.job_store.close()
    if args.check:
        if not target.exists() or target.read_text(encoding="utf-8") != content:
            print("OpenAPI desactualizado; ejecute python scripts/web/export_openapi.py")
            return 1
    else:
        target.write_text(content, encoding="utf-8")
        print(f"Generado {target.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
