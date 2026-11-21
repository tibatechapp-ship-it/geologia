"""CLI for local, reviewed scientific text and built-in core notes."""
import argparse
import json
import sqlite3

from geologia.knowledge import ingest_document, seed_core_knowledge


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Index local UTF-8 geoscience text; no remote sources are downloaded."
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Local .txt, .md, .csv, or .json file to ingest",
    )
    parser.add_argument(
        "--seed-core",
        action="store_true",
        help="Index GEOLOGIA-authored bilingual core checklists",
    )
    parser.add_argument("--source-id", help="Stable bibliographic/source ID")
    parser.add_argument("--title")
    parser.add_argument("--language", help="Original language code (ar/en/ru/zh...)")
    parser.add_argument("--license-name", help="Exact license or permission basis")
    parser.add_argument(
        "--license-status",
        choices=["public_domain", "open_license", "permission", "original_work"],
    )
    parser.add_argument("--reviewed-by", help="Human reviewer or rights-holder")
    parser.add_argument("--review-date", help="License review date: YYYY-MM-DD")
    parser.add_argument("--source-url", default="")
    parser.add_argument("--doi", default="")
    parser.add_argument("--author", default="")
    parser.add_argument("--publisher", default="")
    args = parser.parse_args(argv)

    if args.seed_core:
        if args.path:
            parser.error("do not provide a file path with --seed-core")
        result = seed_core_knowledge()
    else:
        if not args.path:
            parser.error("provide a file path or use --seed-core")
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
