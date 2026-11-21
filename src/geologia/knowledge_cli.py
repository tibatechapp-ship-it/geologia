"""CLI for explicit, license-reviewed local knowledge indexing."""
import argparse
from datetime import date
import json
import sqlite3
import sys

from geologia.knowledge import ingest_document


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Index a local UTF-8 geoscience text file after license review."
    )
    parser.add_argument("path", help="Local .txt, .md, .csv, or .json file; never downloaded")
    parser.add_argument("--source-id", required=True, help="Stable bibliographic/source ID")
    parser.add_argument("--title", required=True)
    parser.add_argument("--language", required=True, help="Original language code (ar/en/ru/zh...)")
    parser.add_argument("--license-name", required=True, help="Exact license or permission basis")
    parser.add_argument(
        "--license-status",
        required=True,
        choices=["public_domain", "open_license", "permission", "original_work"],
    )
    parser.add_argument("--reviewed-by", required=True, help="Human reviewer or rights-holder")
    parser.add_argument("--review-date", required=True, help="License review date: YYYY-MM-DD")
    parser.add_argument("--source-url", default="")
    parser.add_argument("--doi", default="")
    parser.add_argument("--author", default="")
    parser.add_argument("--publisher", default="")
    args = parser.parse_args(argv)
    metadata = {
        "source_id": args.source_id,
        "title": args.title,
        "language": args.language,
        "license_name": args.license_name,
        "license_status": args.license_status,
        "reviewed_by": args.reviewed_by,
        "review_date": args.review_date,
        "source_url": args.source_url,
        "doi": args.doi,
        "author": args.author,
        "publisher": args.publisher,
    }
    try:
        result = ingest_document(args.path, metadata)
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
