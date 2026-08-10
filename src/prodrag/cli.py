from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from pydantic import BaseModel

from prodrag.config import SUPPORTED_EXTENSIONS
from prodrag.container import (
    get_index,
    get_ingestion_service,
    get_query_service,
)
from prodrag.models import QueryRequest


def _default_document_id(path: Path) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", path.stem).strip("-.")[:100] or "document"


def _model_json(model: BaseModel, *, indent: int | None = None) -> str:
    """Serialize safely for legacy Windows consoles such as cp1252 PowerShell."""
    return model.model_dump_json(indent=indent, ensure_ascii=True)


def _ingest(args: argparse.Namespace) -> int:
    source = Path(args.path).resolve(strict=True)
    paths = (
        sorted(path for path in source.iterdir() if path.suffix.lower() in SUPPORTED_EXTENSIONS)
        if source.is_dir()
        else [source]
    )
    if not paths:
        raise SystemExit("No supported documents found")
    if args.document_id and len(paths) != 1:
        raise SystemExit("--document-id can only be used with one file")

    service = get_ingestion_service()
    for path in paths:
        result = service.ingest(
            path,
            document_id=args.document_id or _default_document_id(path),
            tenant_id=args.tenant,
            product=args.product,
            version=args.version,
        )
        print(_model_json(result))
    return 0


def _query(args: argparse.Namespace) -> int:
    response = get_query_service().query(
        QueryRequest(
            question=args.question,
            tenant_id=args.tenant,
            product=args.product,
            version=args.version,
        )
    )
    print(_model_json(response, indent=2))
    return 0


def _delete(args: argparse.Namespace) -> int:
    get_index().delete_document(args.document_id, tenant_id=args.tenant)
    print(json.dumps({"deleted": args.document_id, "tenant_id": args.tenant}))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Operate the prodRAG service")
    commands = parser.add_subparsers(required=True)

    ingest = commands.add_parser("ingest", help="Synchronously ingest a file or directory")
    ingest.add_argument("path")
    ingest.add_argument("--document-id")
    ingest.add_argument("--tenant", default="default")
    ingest.add_argument("--product")
    ingest.add_argument("--version")
    ingest.set_defaults(handler=_ingest)

    query = commands.add_parser("query", help="Run retrieval and grounded answering")
    query.add_argument("question")
    query.add_argument("--tenant", default="default")
    query.add_argument("--product")
    query.add_argument("--version")
    query.set_defaults(handler=_query)

    delete = commands.add_parser("delete", help="Delete a document from the local index")
    delete.add_argument("document_id")
    delete.add_argument("--tenant", default="default")
    delete.set_defaults(handler=_delete)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
