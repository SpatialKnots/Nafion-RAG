from __future__ import annotations

import time


def main() -> None:
    # Phase 1 keeps the worker process alive; queued background ingestion is added next.
    while True:
        time.sleep(30)


if __name__ == "__main__":
    main()
