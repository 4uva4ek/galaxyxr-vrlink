"""Entry point: `python -m galaxyxr_vrlink` (GUI) or `python -m galaxyxr_vrlink --status` (console)."""
from __future__ import annotations

import json
import sys


def main() -> int:
    if "--status" in sys.argv:
        from . import status

        s = status.collect()
        print(json.dumps(s.__dict__, indent=2, default=str))
        return 0
    if "--install" in sys.argv:
        from . import installer, steamvr

        res = installer.install(steamvr.discover())
        print("\n".join(res.messages))
        return 0 if res.ok else 1
    if "--uninstall" in sys.argv:
        from . import installer, steamvr

        res = installer.uninstall(steamvr.discover())
        print("\n".join(res.messages))
        return 0 if res.ok else 1
    from . import gui

    gui.main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
