from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_package():
    package_dir = Path(__file__).with_name("silver_to_gold")
    package_init = package_dir / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        "transform._silver_to_gold_pkg",
        package_init,
        submodule_search_locations=[str(package_dir)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load silver_to_gold package from {package_init}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_package = _load_package()
main = _package.main


if __name__ == "__main__":
    main()
