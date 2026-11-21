"""CLI for local, reviewed scientific text and built-in core notes."""
import argparse
import json
import sqlite3

from geologia.knowledge import ingest_document, search, seed_core_knowledge


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Index local UTF-8 text or PDF geoscience sources; "
            "no remote sources are downloaded."
        )
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Local .txt, .md, .csv, .json, or .pdf file to ingest (.pdf requires the pdf extra)",
    )
    parser.add_argument(
        "--seed-core",
        action="store_true",
        help="Index GEOLOGIA-authored multilingual core checklists",
    )
    parser.add_argument(
        "--search",
        metavar="QUERY",
        help="Search the local knowledge index without network or model access",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum local search results (1-20; default: 5)",
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
    parser.add_argument(
        "--source-kind",
        choices=[
            "research_article", "review_article", "official_dataset",
            "technical_report", "textbook", "field_observation", "core_note",
            "preprint", "other",
        ],
        default="other",
        help="Evidence source type; does not imply scientific validation",
    )
    parser.add_argument(
        "--scientific-review-status",
        choices=["not_assessed", "editorial_reviewed", "subject_matter_reviewed"],
        default="not_assessed",
        help="Separate from license review; defaults to not_assessed",
    )
    parser.add_argument("--scientific-reviewed-by", default="")
    parser.add_argument("--scientific-review-date", default="")
    args = parser.parse_args(argv)

    if args.search is not None:
        if args.path or args.seed_core:
            parser.error("do not combine --search with a file path or --seed-core")
        try:
            result = search(args.search, limit=args.limit)
        except (ValueError, OSError, sqlite3.Error) as exc:
            parser.error(str(exc))
    elif args.seed_core:
        if args.path:
            parser.error("do not provide a file path with --seed-core")
        result = seed_core_knowledge()
    else:
        if not args.path:
            parser.error("provide a file path, use --seed-core, or use --search QUERY")
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
            "source_kind": args.source_kind,
            "scientific_review_status": args.scientific_review_status,
            "scientific_reviewed_by": args.scientific_reviewed_by,
            "scientific_review_date": args.scientific_review_date,
        }
        try:
            result = ingest_document(args.path, metadata)
        except (ValueError, OSError, sqlite3.Error) as exc:
            parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
