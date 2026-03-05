#!/usr/bin/env python3
import argparse
import base64
import csv
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

try:
    import requests
except Exception:  # pragma: no cover - handled at runtime
    requests = None

try:
    from PIL import ExifTags, Image
except Exception:  # pragma: no cover - handled at runtime
    ExifTags = None
    Image = None

try:
    from iptcinfo3 import IPTCInfo
except Exception:  # pragma: no cover - optional dependency behavior
    IPTCInfo = None


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg"}
ADOBE_CATEGORIES = {
    1: "Animals",
    2: "Buildings and Architecture",
    3: "Business",
    4: "Drinks",
    5: "The Environment",
    6: "States of Mind",
    7: "Food",
    8: "Graphic Resources",
    9: "Hobbies and Leisure",
    10: "Industry",
    11: "Landscape",
    12: "Lifestyle",
    13: "People",
    14: "Plants and Flowers",
    15: "Culture and Religion",
    16: "Science",
    17: "Social Issues",
    18: "Sports",
    19: "Technology",
    20: "Transport",
    21: "Travel",
}


class FotowordError(Exception):
    pass


def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def infer_category(title: str, description: str, keywords_field: str) -> str:
    text = f"{title} {description} {keywords_field}".lower()
    rules = [
        (1, ["animal", "bird", "duck", "dog", "cat", "wildlife", "pet", "insect"]),
        (7, ["food", "meal", "dish", "eat", "cuisine", "snack"]),
        (4, ["drink", "beverage", "wine", "beer", "coffee", "tea", "cocktail"]),
        (13, ["person", "people", "portrait", "man", "woman", "child"]),
        (14, ["flower", "plant", "blossom", "botanical"]),
        (18, ["sport", "fitness", "soccer", "basketball", "yoga", "ski"]),
        (19, ["technology", "computer", "smartphone", "device", "digital", "ai"]),
        (20, ["car", "bus", "train", "plane", "transport", "vehicle"]),
        (2, ["building", "architecture", "interior", "office", "house", "temple"]),
        (11, ["landscape", "mountain", "nature", "cityscape", "vista", "scenery"]),
        (5, ["environment", "climate", "ecology", "sustainability"]),
        (3, ["business", "finance", "money", "office", "corporate"]),
        (16, ["science", "medical", "laboratory", "research"]),
        (10, ["industry", "factory", "manufacturing", "energy", "construction"]),
        (21, ["travel", "tourism", "destination", "vacation"]),
        (9, ["hobby", "leisure", "knitting", "sailing", "craft"]),
        (12, ["lifestyle", "home life", "daily life", "wellness"]),
        (15, ["culture", "religion", "ritual", "tradition", "spiritual"]),
        (17, ["poverty", "inequality", "politics", "violence", "social issue"]),
        (6, ["emotion", "sad", "happy", "anxiety", "state of mind"]),
        (8, ["background", "texture", "pattern", "symbol", "graphic"]),
    ]
    for category_id, needles in rules:
        if any(needle in text for needle in needles):
            return str(category_id)
    return "11"


def fit_description_length(text: str) -> str:
    text = " ".join(text.split()).strip()
    if len(text) > 200:
        cut = text[:200]
        last_space = cut.rfind(" ")
        text = cut[:last_space] if last_space > 150 else cut
    while len(text) < 175:
        pad = " for commercial and editorial stock usage"
        if len(text) + len(pad) > 200:
            text = (text + pad)[:200].rstrip()
            break
        text += pad
    return text.rstrip(". ") + "."


def pick_match(tokens: Sequence[str], options: Sequence[Tuple[str, Sequence[str]]], default: str) -> str:
    for value, needles in options:
        for t in tokens:
            if any(n in t for n in needles):
                return value
    return default


def build_structured_description(title: str, raw_description: str, keywords_field: str) -> str:
    tokens = [t.strip().lower() for t in keywords_field.split(",") if t.strip()]
    subject = " ".join(title.split()[:4]).strip() or "subject"

    activity = pick_match(
        tokens,
        [
            ("captured interacting naturally", ("play", "eat", "walk", "run", "rest", "graz", "fly", "swim")),
            ("shown in a still moment", ("portrait", "closeup", "still", "pose")),
            ("presented in a natural scene", ("nature", "wildlife", "outdoor")),
        ],
        "shown clearly in the frame",
    )
    location_type = pick_match(tokens, [("outdoor", ("outdoor", "nature", "wild", "park")), ("indoor", ("indoor", "interior", "studio", "room"))], "outdoor")
    environment = pick_match(
        tokens,
        [
            ("with snowy surroundings", ("snow", "winter", "ice")),
            ("with urban surroundings", ("city", "street", "urban")),
            ("in a natural environment", ("nature", "forest", "field", "water", "lake", "mountain")),
        ],
        "in a clean visual environment",
    )
    daytime = pick_match(tokens, [("daylight", ("day", "sunlight", "morning", "afternoon")), ("golden-hour light", ("sunset", "sunrise", "golden")), ("night light", ("night", "dark", "evening"))], "daylight")
    mood = pick_match(tokens, [("calm", ("calm", "peaceful", "quiet")), ("warm", ("warm", "cozy", "friendly")), ("energetic", ("active", "energy", "dynamic"))], "natural")
    purposes = pick_match(
        tokens,
        [
            ("wildlife, conservation, and nature education content", ("animal", "bird", "wildlife", "nature")),
            ("travel, outdoor, and lifestyle campaigns", ("travel", "landscape", "outdoor", "lifestyle")),
            ("marketing, editorial, and web storytelling", ("business", "technology", "people", "city")),
        ],
        "marketing, editorial, and digital storytelling",
    )

    base = (
        f"{subject} {activity} in an {location_type} setting, {environment}, under {daytime}, "
        f"with a {mood} mood, suitable for {purposes}"
    )
    if raw_description.strip():
        base = f"{base}, reflecting {raw_description.strip().rstrip('.')}"

    return fit_description_length(base)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate stock metadata CSVs from local JPGs using Ollama.")
    parser.add_argument("--input", required=True, help="Directory containing JPG/JPEG files")
    parser.add_argument("--out", default="./out", help="Output directory for platform CSV files")
    parser.add_argument("--model", default="llava:7b", help="Ollama model name")
    parser.add_argument("--keywords", type=int, default=40, help="Number of keywords per image")
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
    parser.add_argument("--config", default="config/defaults.json", help="Path to config JSON")
    parser.add_argument("--recursive", action="store_true", help="Recursively scan input directory")
    parser.add_argument("--dry-run", action="store_true", help="List files that would be processed")
    return parser.parse_args()


def load_config(config_path: Path) -> Dict:
    if not config_path.exists():
        raise FotowordError(f"Config file not found: {config_path}")
    try:
        with config_path.open("r", encoding="utf-8") as f:
            cfg = json.load(f)
    except json.JSONDecodeError as exc:
        raise FotowordError(f"Invalid JSON in config file {config_path}: {exc}") from exc

    platforms = cfg.get("platforms")
    if not isinstance(platforms, dict) or not platforms:
        raise FotowordError("Config must define non-empty object: platforms")

    for platform_name, headers in platforms.items():
        if not isinstance(headers, list) or not headers:
            raise FotowordError(f"Platform '{platform_name}' must map to a non-empty list of headers")
        if not any(str(header).lower() == "filename" for header in headers):
            raise FotowordError(f"Platform '{platform_name}' headers must include 'filename'")

    cfg.setdefault("ollama_url", "http://localhost:11434")
    return cfg


def scan_images(input_dir: Path, recursive: bool) -> List[Path]:
    if not input_dir.exists() or not input_dir.is_dir():
        raise FotowordError(f"Input path is not a directory: {input_dir}")

    iterator: Iterable[Path]
    if recursive:
        iterator = input_dir.rglob("*")
    else:
        iterator = input_dir.iterdir()

    files = [p for p in iterator if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
    files.sort(key=lambda p: p.name.lower())
    return files


def csv_path_for_platform(out_dir: Path, platform: str) -> Path:
    return out_dir / f"{platform}.csv"


def ensure_csv_with_header(path: Path, headers: Sequence[str]) -> None:
    if path.exists() and path.stat().st_size > 0:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(headers), extrasaction="ignore")
        writer.writeheader()


def load_existing_filenames(out_dir: Path, platforms: Dict[str, Sequence[str]]) -> Set[str]:
    seen: Set[str] = set()
    for platform in platforms:
        path = csv_path_for_platform(out_dir, platform)
        if not path.exists() or path.stat().st_size == 0:
            continue
        with path.open("r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                continue
            filename_col = next((col for col in reader.fieldnames if col and col.lower() == "filename"), None)
            if not filename_col:
                continue
            for row in reader:
                name = (row.get(filename_col) or "").strip()
                if name:
                    seen.add(name)
    return seen


def extract_exif(image_path: Path) -> Dict[str, str]:
    metadata: Dict[str, str] = {}
    if Image is None or ExifTags is None:
        return metadata
    try:
        with Image.open(image_path) as img:
            raw_exif = img.getexif()
            if not raw_exif:
                return metadata

            exif_map = {
                ExifTags.TAGS.get(tag, str(tag)): value
                for tag, value in raw_exif.items()
            }

            wanted = [
                "Make",
                "Model",
                "LensModel",
                "FocalLength",
                "FNumber",
                "ExposureTime",
                "ISOSpeedRatings",
                "DateTimeOriginal",
            ]

            for key in wanted:
                if key in exif_map:
                    metadata[key] = str(exif_map[key])
    except Exception:
        return metadata

    return metadata


def decode_iptc_value(value) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="ignore").strip()
    return str(value).strip()


def extract_iptc(image_path: Path) -> Dict[str, str]:
    if IPTCInfo is None:
        return {}

    try:
        info = IPTCInfo(str(image_path), force=True)
    except Exception:
        return {}

    result: Dict[str, str] = {}
    wanted = {
        "caption/abstract": "iptc_caption",
        "object name": "iptc_title",
        "keywords": "iptc_keywords",
    }

    for source_key, target_key in wanted.items():
        try:
            value = info[source_key]
        except Exception:
            value = None
        if not value:
            continue
        if isinstance(value, list):
            joined = ", ".join([decode_iptc_value(v) for v in value if decode_iptc_value(v)])
            if joined:
                result[target_key] = joined
        else:
            decoded = decode_iptc_value(value)
            if decoded:
                result[target_key] = decoded

    return result


def summarize_metadata(exif_data: Dict[str, str], iptc_data: Dict[str, str]) -> str:
    parts: List[str] = []
    if exif_data:
        exif_text = "; ".join(f"{k}: {v}" for k, v in exif_data.items())
        parts.append(f"EXIF: {exif_text}")
    if iptc_data:
        iptc_text = "; ".join(f"{k}: {v}" for k, v in iptc_data.items())
        parts.append(f"IPTC: {iptc_text}")
    return " | ".join(parts)


def build_prompt(filename: str, keyword_count: int, metadata_summary: str) -> str:
    category_list = "; ".join(f"{k}={v}" for k, v in ADOBE_CATEGORIES.items())
    prompt = (
        "You are generating metadata for stock photography. "
        "Be factual and neutral. Avoid brands/trademarks. "
        "Do not include person names unless clearly visible in the image. "
        f"Return strict JSON only with keys: title, description, keywords, category. "
        f"keywords should be an array of up to {keyword_count} concise keyword strings. "
        f"category must be an integer from 1 to 21 using this mapping: {category_list}. "
        "title should be 6-12 words. description should be factual and concise. "
        f"Image filename: {filename}."
    )
    if metadata_summary:
        prompt += f" Metadata context (may be incomplete): {metadata_summary}."
    return prompt


def check_ollama_available(base_url: str, timeout: int = 5) -> None:
    if requests is None:
        raise FotowordError("Missing dependency 'requests'. Install with: pip install -r requirements.txt")
    url = base_url.rstrip("/") + "/api/tags"
    try:
        response = requests.get(url, timeout=timeout)
    except requests.RequestException as exc:
        raise FotowordError(
            f"Ollama is unreachable at {base_url}. Ensure Ollama is running on localhost:11434."
        ) from exc

    if response.status_code >= 400:
        raise FotowordError(
            f"Ollama health check failed at {url} with status {response.status_code}: {response.text[:200]}"
        )


def extract_json_block(text: str) -> str:
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0)
    return text


def normalize_keywords(raw_keywords, desired_count: int) -> List[str]:
    if isinstance(raw_keywords, str):
        candidates = [part.strip() for part in re.split(r"[,;\n]", raw_keywords) if part.strip()]
    elif isinstance(raw_keywords, list):
        candidates = [str(k).strip() for k in raw_keywords if str(k).strip()]
    else:
        candidates = []

    normalized: List[str] = []
    seen = set()
    for keyword in candidates:
        cleaned = keyword.lower().strip().strip(".")
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
        if len(normalized) >= desired_count:
            break

    return normalized


def parse_partial_json_fields(text: str, desired_keywords: int) -> Tuple[str, str, str, str]:
    title_match = re.search(r'"title"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
    desc_match = re.search(r'"description"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
    keywords_match = re.search(r'"keywords"\s*:\s*\[(.*)', text, re.DOTALL)
    category_match = re.search(r'"category"\s*:\s*(\d+)', text, re.DOTALL)

    title = ""
    description = ""
    keyword_field = ""
    category = ""

    if title_match:
        title = bytes(title_match.group(1), "utf-8").decode("unicode_escape").strip()
    if desc_match:
        description = bytes(desc_match.group(1), "utf-8").decode("unicode_escape").strip()

    if keywords_match:
        # Handle truncated arrays by extracting whatever quoted items are present.
        raw_items = re.findall(r'"((?:[^"\\]|\\.)*)"', keywords_match.group(1))
        decoded_items = [bytes(item, "utf-8").decode("unicode_escape") for item in raw_items]
        normalized = normalize_keywords(decoded_items, desired_keywords)
        if normalized:
            keyword_field = ", ".join(normalized)
    if category_match:
        candidate = category_match.group(1).strip()
        if candidate.isdigit() and 1 <= int(candidate) <= 21:
            category = candidate

    if not title:
        raise ValueError("Missing title")
    if not description:
        raise ValueError("Missing description")
    if not keyword_field:
        raise ValueError("Missing keywords")
    description = build_structured_description(title, description, keyword_field)
    if not category:
        category = infer_category(title, description, keyword_field)

    return title, description, keyword_field, category


def parse_model_response(response_text: str, desired_keywords: int) -> Tuple[str, str, str, str]:
    json_text = extract_json_block(response_text)
    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError:
        return parse_partial_json_fields(json_text, desired_keywords)

    title = str(payload.get("title", "")).strip()
    description = str(payload.get("description", "")).strip()
    keywords = normalize_keywords(payload.get("keywords", []), desired_keywords)
    category_value = payload.get("category")
    category = ""
    if isinstance(category_value, int):
        if 1 <= category_value <= 21:
            category = str(category_value)
    elif isinstance(category_value, str) and category_value.strip().isdigit():
        c = int(category_value.strip())
        if 1 <= c <= 21:
            category = str(c)

    if not title:
        raise ValueError("Missing title")
    if not description:
        raise ValueError("Missing description")
    if not keywords:
        raise ValueError("Missing keywords")

    keyword_field = ", ".join(keywords)
    description = build_structured_description(title, description, keyword_field)
    if not category:
        category = infer_category(title, description, keyword_field)
    return title, description, keyword_field, category


def generate_metadata(
    image_path: Path,
    model: str,
    ollama_url: str,
    keyword_count: int,
    timeout: int = 300,
) -> Tuple[str, str, str, str]:
    if requests is None:
        raise FotowordError("Missing dependency 'requests'. Install with: pip install -r requirements.txt")
    with image_path.open("rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("ascii")

    exif_data = extract_exif(image_path)
    iptc_data = extract_iptc(image_path)
    metadata_summary = summarize_metadata(exif_data, iptc_data)
    prompt = build_prompt(image_path.name, keyword_count, metadata_summary)

    url = ollama_url.rstrip("/") + "/api/generate"
    body = {
        "model": model,
        "prompt": prompt,
        "format": "json",
        "images": [image_b64],
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 768,
        },
    }

    last_error: Optional[Exception] = None
    for _ in range(2):
        try:
            response = requests.post(url, json=body, timeout=(10, timeout))
            response.raise_for_status()
            data = response.json()
            raw_text = str(data.get("response", ""))
            return parse_model_response(raw_text, keyword_count)
        except (requests.RequestException, json.JSONDecodeError, ValueError) as exc:
            last_error = exc

    raise FotowordError(f"Failed to generate valid metadata for {image_path.name}: {last_error}")


def platform_row(
    platform: str,
    filename: str,
    headers: Sequence[str],
    title: str,
    description: str,
    keywords: str,
    category: str,
) -> Dict[str, str]:
    platform_key = platform.lower()
    if platform_key == "adobe":
        # Adobe format requested:
        # Filename = image filename, Title = generated description, Keywords unchanged, Category empty.
        base = {
            "filename": filename,
            "title": description,
            "keywords": keywords,
            "category": category,
        }
    else:
        base = {
            "filename": filename,
            "title": title,
            "description": description,
            "keywords": keywords,
        }
    return {header: base.get(header.lower(), "") for header in headers}


def open_writers(out_dir: Path, platforms: Dict[str, Sequence[str]]):
    file_handles = {}
    writers = {}
    try:
        for platform, headers in platforms.items():
            path = csv_path_for_platform(out_dir, platform)
            ensure_csv_with_header(path, headers)
            fh = path.open("a", newline="", encoding="utf-8")
            writer = csv.DictWriter(fh, fieldnames=list(headers), extrasaction="ignore")
            file_handles[platform] = fh
            writers[platform] = writer
    except Exception:
        for fh in file_handles.values():
            fh.close()
        raise
    return file_handles, writers


def run() -> int:
    args = parse_args()

    input_dir = Path(args.input).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve()

    try:
        cfg = load_config(config_path)
        platforms: Dict[str, Sequence[str]] = cfg["platforms"]
        ollama_url = cfg.get("ollama_url", "http://localhost:11434")

        if args.keywords <= 0:
            raise FotowordError("--keywords must be > 0")

        images = scan_images(input_dir, args.recursive)
        existing = load_existing_filenames(out_dir, platforms) if args.skip_existing else set()

        to_process = [p for p in images if p.name not in existing]

        print(f"Found {len(images)} JPG(s); {len(existing)} existing; {len(to_process)} to process.")

        if args.dry_run:
            for p in to_process:
                print(str(p))
            return 0

        if not to_process:
            print("No new files to process.")
            return 0

        check_ollama_available(ollama_url)

        out_dir.mkdir(parents=True, exist_ok=True)
        files, writers = open_writers(out_dir, platforms)

        processed = 0
        skipped = len(images) - len(to_process)
        failed = 0

        try:
            for image_path in to_process:
                try:
                    print(f"{now_ts()} Starting: {image_path.name}")
                    title, description, keywords, category = generate_metadata(
                        image_path=image_path,
                        model=args.model,
                        ollama_url=ollama_url,
                        keyword_count=args.keywords,
                        timeout=args.timeout,
                    )
                    for platform, headers in platforms.items():
                        row = platform_row(platform, image_path.name, headers, title, description, keywords, category)
                        writers[platform].writerow(row)
                    processed += 1
                    print(f"{now_ts()} Processed: {image_path.name}")
                except Exception as exc:
                    failed += 1
                    print(f"Failed: {image_path.name} ({exc})", file=sys.stderr)
        finally:
            for fh in files.values():
                fh.close()

        print(f"Summary: processed={processed}, skipped={skipped}, failed={failed}")
        return 0 if failed == 0 else 1

    except FotowordError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
