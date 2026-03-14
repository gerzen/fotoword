import argparse
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Set

from fotoword_app.config import load_config
from fotoword_app.engine import (
    check_ollama_available,
    csv_path_for_platform,
    generate_metadata,
    load_metadata_map,
    normalized_metadata_row,
    now_ts,
    platform_row,
    scan_images,
    write_metadata_csv,
    write_platform_csv,
)
from fotoword_app.errors import FotowordError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate stock metadata CSVs from local JPGs using Ollama.")
    parser.add_argument(
        "--input",
        default=".",
        help="Directory containing JPG/JPEG files (default: current directory)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output directory for platform CSV files (default: <input>/out)",
    )
    parser.add_argument("--model", default="llava:7b", help="Ollama model name")
    parser.add_argument("--keywords", type=int, default=50, help="Number of keywords per image")
    parser.add_argument(
        "--analysis-max-side",
        type=int,
        default=1536,
        help="Max width/height in pixels for model analysis image (default: 1536)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Ollama read timeout in seconds for each image (default: 300)",
    )
    parser.add_argument(
        "--skip-existing",
        dest="skip_existing",
        action="store_true",
        default=True,
        help="Skip images already present in any output CSV (default: enabled)",
    )
    parser.add_argument(
        "--no-skip-existing",
        dest="skip_existing",
        action="store_false",
        help="Do not skip images already present in output CSVs",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to config JSON (default: bundled config/defaults.json)",
    )
    parser.add_argument("--recursive", action="store_true", help="Recursively scan input directory")
    parser.add_argument("--dry-run", action="store_true", help="List files that would be processed")
    return parser.parse_args()


def run() -> int:
    args = parse_args()

    script_dir = Path(__file__).resolve().parent.parent
    input_dir = Path(args.input).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve() if args.out else (input_dir / "out")
    config_path = Path(args.config).expanduser().resolve() if args.config else (script_dir / "config" / "defaults.json")

    try:
        cfg = load_config(config_path)
        platforms: Dict[str, Sequence[str]] = cfg["platforms"]
        ollama_url = cfg.get("ollama_url", "http://localhost:11434")

        if args.keywords <= 0:
            raise FotowordError("--keywords must be > 0")

        images = scan_images(input_dir, args.recursive)
        metadata_map = load_metadata_map(out_dir)
        existing = set(metadata_map.keys()) if args.skip_existing else set()
        to_process = [p for p in images if p.name not in existing]

        print(f"Found {len(images)} JPG(s); {len(existing)} existing; {len(to_process)} to process.")

        if args.dry_run:
            for p in to_process:
                print(str(p))
            return 0

        if to_process:
            check_ollama_available(ollama_url)

        out_dir.mkdir(parents=True, exist_ok=True)

        processed = 0
        reused = 0
        failed = 0
        failed_names: Set[str] = set()

        for image_path in images:
            existing_row = metadata_map.get(image_path.name)
            if existing_row and args.skip_existing:
                reused += 1
                continue
            try:
                print(f"{now_ts()} Starting: {image_path.name}")
                title, description, keywords, category, purpose = generate_metadata(
                    image_path=image_path,
                    model=args.model,
                    ollama_url=ollama_url,
                    keyword_count=args.keywords,
                    analysis_max_side=args.analysis_max_side,
                    timeout=args.timeout,
                )
                metadata_map[image_path.name] = {
                    "filename": image_path.name,
                    "title": title,
                    "description": description,
                    "keywords": keywords,
                    "category": category,
                    "purpose": purpose,
                }
                processed += 1
                print(f"{now_ts()} Processed: {image_path.name}")
            except Exception as exc:
                failed += 1
                failed_names.add(image_path.name)
                print(f"Failed: {image_path.name} ({exc})", file=sys.stderr)

        platform_rows: Dict[str, List[Dict[str, str]]] = {p: [] for p in platforms}
        for filename in sorted(metadata_map.keys(), key=lambda s: s.lower()):
            if filename in failed_names:
                continue
            meta = normalized_metadata_row(filename, metadata_map[filename])
            for platform, headers in platforms.items():
                row = platform_row(
                    platform=platform,
                    filename=filename,
                    headers=headers,
                    title=meta["title"],
                    description=meta["description"],
                    keywords=meta["keywords"],
                    category=meta["category"],
                    purpose=meta["purpose"],
                )
                platform_rows[platform].append(row)

        for platform, headers in platforms.items():
            write_platform_csv(csv_path_for_platform(out_dir, platform), headers, platform_rows[platform])

        write_metadata_csv(out_dir, metadata_map)

        print(f"Summary: processed={processed}, reused={reused}, failed={failed}")
        return 0 if failed == 0 else 1

    except FotowordError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


def main() -> None:
    sys.exit(run())
