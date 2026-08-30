from __future__ import annotations

import os
from pathlib import Path

from identity.bigballs import build_completeness_audit, run_bigballs_identity_audit


def main() -> None:
    data_dir = Path(os.getenv("FOOTBALL_SCOUT_DATA_DIR", "data"))
    print({"identity": run_bigballs_identity_audit(data_dir)})
    print(build_completeness_audit(data_dir))


if __name__ == "__main__":
    main()
