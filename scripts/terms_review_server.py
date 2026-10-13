"""Run just the local Terms workbench; no PostgreSQL or ingestion startup required."""
from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from app.terms.review_ui import review_root, router


def create_app(root: Path) -> FastAPI:
    app = FastAPI(title="ARIADNE Terms review")
    app.include_router(router)
    app.dependency_overrides[review_root] = lambda: root.resolve()
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("data/reviews/terms"))
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    uvicorn.run(create_app(args.root), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
