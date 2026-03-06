#!/usr/bin/env python3
import argparse
import base64
import csv
import io
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
SHUTTERSTOCK_CATEGORIES = [
    "Abstract",
    "Animals/Wildlife",
    "Arts",
    "Backgrounds/Textures",
    "Beauty/Fashion",
    "Buildings/Landmarks",
    "Business/Finance",
    "Celebrities",
    "Education",
    "Food and Drink",
    "Healthcare/Medical",
    "Holidays",
    "Industrial",
    "Interiors",
    "Miscellaneous",
    "Nature",
    "Objects",
    "Parks/Outdoor",
    "People",
    "Religion",
    "Science",
    "Signs/Symbols",
    "Sports/Recreation",
    "Technology",
    "Transportation",
    "Vintage",
]
DREAMSTIME_MAX_KEYWORDS = 50
METADATA_HEADERS = [
    "filename",
    "title",
    "description",
    "keywords",
    "category",
]
DREAMSTIME_CATEGORY_RULES = [
    (168, ["animal", "bird", "duck", "dog", "cat", "wildlife", "pet", "insect"]),
    (31, ["bird"]),
    (30, ["pet"]),
    (146, ["landscape", "scenery", "vista", "nature"]),
    (16, ["river", "lake", "stream"]),
    (19, ["ocean", "sea", "coast"]),
    (15, ["mountain"]),
    (25, ["flower", "garden", "blossom"]),
    (12, ["plant", "tree", "vegetation"]),
    (171, ["water"]),
    (123, ["active", "activity"]),
    (162, ["portrait", "headshot"]),
    (119, ["child", "children", "kid"]),
    (117, ["man", "male"]),
    (116, ["woman", "female"]),
    (118, ["family", "families"]),
    (75, ["business people", "office people"]),
    (80, ["finance", "money", "banking"]),
    (79, ["communications", "meeting", "presentation"]),
    (71, ["building", "architecture"]),
    (73, ["interior", "indoor", "room"]),
    (72, ["outdoor"]),
    (70, ["landmark"]),
    (127, ["food", "meal", "dish", "cuisine", "eat"]),
    (137, ["fruit", "vegetable"]),
    (157, ["sport", "fitness", "yoga", "soccer", "basketball", "recreation"]),
    (98, ["transport", "car", "bus", "train", "plane", "boat", "vehicle"]),
    (105, ["computer", "laptop", "desktop", "software"]),
    (104, ["telecommunications", "phone", "mobile"]),
    (210, ["artificial intelligence", "ai"]),
    (92, ["medical", "health", "healthcare", "doctor", "hospital"]),
    (150, ["education", "school", "student", "classroom"]),
    (128, ["religion", "religious", "spiritual", "faith"]),
    (112, ["background", "texture", "pattern"]),
    (199, ["web background", "web texture"]),
    (145, ["object", "still life", "item"]),
    (152, ["retro", "vintage"]),
    (61, ["travel", "destination", "tourism", "vacation"]),
    (190, ["christmas"]),
    (193, ["easter"]),
    (192, ["halloween"]),
    (189, ["new year"]),
]


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


def infer_shutterstock_categories(title: str, description: str, keywords_field: str) -> str:
    text = f"{title} {description} {keywords_field}".lower()
    rules = [
        ("Animals/Wildlife", ["animal", "bird", "duck", "dog", "cat", "wildlife", "pet", "insect"]),
        ("People", ["person", "people", "portrait", "man", "woman", "child", "face", "hand"]),
        ("Food and Drink", ["food", "meal", "dish", "eat", "drink", "beverage", "coffee", "tea"]),
        ("Nature", ["nature", "plant", "flower", "forest", "lake", "mountain", "snow", "water"]),
        ("Parks/Outdoor", ["outdoor", "park", "camp", "hiking", "garden", "playground"]),
        ("Buildings/Landmarks", ["building", "architecture", "landmark", "temple", "bridge"]),
        ("Interiors", ["interior", "room", "kitchen", "bedroom", "office interior"]),
        ("Business/Finance", ["business", "finance", "money", "office", "corporate"]),
        ("Technology", ["technology", "computer", "smartphone", "device", "ai", "virtual reality"]),
        ("Science", ["science", "research", "lab", "medical", "chemistry"]),
        ("Healthcare/Medical", ["health", "medical", "doctor", "hospital", "wellness"]),
        ("Sports/Recreation", ["sport", "fitness", "yoga", "soccer", "basketball", "recreation"]),
        ("Transportation", ["car", "bus", "train", "plane", "boat", "transport"]),
        ("Backgrounds/Textures", ["background", "texture", "pattern", "wallpaper", "flat lay"]),
        ("Signs/Symbols", ["sign", "symbol", "icon", "arrow", "flag", "logo"]),
        ("Education", ["education", "school", "classroom", "book", "graduation"]),
        ("Religion", ["religion", "religious", "spiritual", "worship", "temple"]),
        ("Industrial", ["industrial", "factory", "construction", "mining", "tools"]),
        ("Holidays", ["holiday", "christmas", "easter", "halloween", "ramadan", "vacation"]),
        ("Arts", ["art", "painting", "drawing", "illustration", "artist"]),
        ("Beauty/Fashion", ["fashion", "beauty", "makeup", "hairstyle", "clothing"]),
        ("Vintage", ["vintage", "retro", "sepia", "kitsch"]),
        ("Abstract", ["abstract", "fractal", "blur", "concept"]),
        ("Objects", ["object", "still life", "tool", "item"]),
    ]
    matches: List[str] = []
    for label, needles in rules:
        if any(needle in text for needle in needles):
            matches.append(label)
        if len(matches) >= 2:
            break

    if not matches:
        matches = ["Miscellaneous"]
    return ", ".join(matches[:2])


def infer_dreamstime_categories(title: str, description: str, keywords_field: str) -> Tuple[str, str, str]:
    text = f"{title} {description} {keywords_field}".lower()
    matches: List[str] = []
    for cat_id, needles in DREAMSTIME_CATEGORY_RULES:
        if any(needle in text for needle in needles):
            value = str(cat_id)
            if value not in matches:
                matches.append(value)
        if len(matches) >= 3:
            break

    if not matches:
        matches = ["145"]  # Objects -> Other
    while len(matches) < 3:
        matches.append("0")
    return matches[0], matches[1], matches[2]


def to_dreamstime_keywords(keywords_field: str, max_keywords: int = DREAMSTIME_MAX_KEYWORDS) -> str:
    terms: List[str] = []
    seen = set()
    stop_words = {"a", "an", "the", "keyword", "keywords"}
    for phrase in keywords_field.split(","):
        for token in phrase.strip().split(" "):
            word = re.sub(r"[^a-z0-9-]", "", token.lower().strip())
            if not word or word in stop_words or word in seen:
                continue
            seen.add(word)
            terms.append(word)
            if len(terms) >= max_keywords:
                return ", ".join(terms)
    return ", ".join(terms)


def description_words_fallback(description: str, existing_keywords: Sequence[str], desired_count: int) -> List[str]:
    existing = set(existing_keywords)
    words = re.findall(r"[a-z0-9-]+", description.lower())
    stop_words = {
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "for",
        "with",
        "by",
        "at",
        "from",
        "keyword",
        "keywords",
    }
    out: List[str] = []
    seen = set()
    for w in words:
        if len(w) < 3 or w in stop_words or w in existing or w in seen:
            continue
        seen.add(w)
        out.append(w)
        if len(existing) + len(out) >= desired_count:
            break
    return out


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


def metadata_csv_path(out_dir: Path) -> Path:
    return out_dir / "metadata.csv"


def ensure_csv_with_header(path: Path, headers: Sequence[str]) -> None:
    if path.exists() and path.stat().st_size > 0:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(headers), extrasaction="ignore")
        writer.writeheader()


def load_existing_filenames(out_dir: Path) -> Set[str]:
    seen: Set[str] = set()
    path = metadata_csv_path(out_dir)
    if not path.exists() or path.stat().st_size == 0:
        return seen

    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return seen
        filename_col = next((col for col in reader.fieldnames if col and col.lower() == "filename"), None)
        if not filename_col:
            return seen
        for row in reader:
            name = (row.get(filename_col) or "").strip()
            if name:
                seen.add(name)
    return seen


def load_metadata_map(out_dir: Path) -> Dict[str, Dict[str, str]]:
    path = metadata_csv_path(out_dir)
    result: Dict[str, Dict[str, str]] = {}
    if not path.exists() or path.stat().st_size == 0:
        return result

    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return result
        filename_col = next((col for col in reader.fieldnames if col and col.lower() == "filename"), None)
        if not filename_col:
            return result
        for row in reader:
            name = (row.get(filename_col) or "").strip()
            if not name:
                continue
            result[name] = {k: (v or "") for k, v in row.items()}
    return result


def normalized_metadata_row(filename: str, row: Dict[str, str]) -> Dict[str, str]:
    generic_keywords = (
        row.get("keywords")
        or row.get("adobe_keywords")
        or row.get("shutterstock_keywords")
        or row.get("dreamstime_keywords")
        or ""
    ).strip()
    return {
        "filename": filename,
        "title": (row.get("title") or "").strip(),
        "description": (row.get("description") or "").strip(),
        "keywords": generic_keywords,
        "category": (row.get("category") or "").strip(),
    }


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


def build_analysis_image_bytes(image_path: Path, max_side: int) -> Tuple[bytes, Optional[Tuple[int, int]], Optional[Tuple[int, int]]]:
    with image_path.open("rb") as f:
        original = f.read()

    if Image is None:
        return original, None, None

    if max_side <= 0:
        return original, None, None

    try:
        with Image.open(io.BytesIO(original)) as img:
            width, height = img.size
            longest = max(width, height)
            if longest <= max_side:
                return original, (width, height), (width, height)

            scale = max_side / float(longest)
            new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
            resized = img.convert("RGB").resize(new_size, Image.Resampling.LANCZOS)
            out = io.BytesIO()
            resized.save(out, format="JPEG", quality=90, optimize=True)
            return out.getvalue(), (width, height), new_size
    except Exception:
        return original, None, None


def build_prompt(filename: str, keyword_count: int, metadata_summary: str) -> str:
    category_list = "; ".join(f"{k}={v}" for k, v in ADOBE_CATEGORIES.items())
    prompt = (
        "You are generating metadata for stock photography. "
        "Be factual and neutral. Avoid brands/trademarks. "
        "Do not include person names unless clearly visible in the image. "
        f"Return strict JSON only with keys: title, description, keywords, category. "
        f"keywords must be an array of exactly {keyword_count} strong, unique single-word keywords. "
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
    articles = {"a", "an", "the", "keyword", "keywords"}
    for keyword in candidates:
        cleaned = keyword.lower().replace("_", " ")
        cleaned = re.sub(r"\s+", " ", cleaned).strip().strip(".")
        words: List[str] = []
        seen_words = set()
        for w in cleaned.split(" "):
            if not w or w in articles or w in seen_words:
                continue
            seen_words.add(w)
            words.append(w)
        if not words:
            continue
        cleaned = " ".join(words[:3])
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
        if len(normalized) >= desired_count:
            break

    return normalized


def normalize_single_word_keywords(raw_keywords: Sequence[str], desired_count: int) -> List[str]:
    items: List[str] = []
    seen = set()
    articles = {"a", "an", "the", "keyword", "keywords"}
    for phrase in raw_keywords:
        for token in phrase.split(" "):
            word = re.sub(r"[^a-z0-9-]", "", token.lower().strip())
            if not word or word in articles or word in seen:
                continue
            seen.add(word)
            items.append(word)
            if len(items) >= desired_count:
                return items
    return items


def parse_keywords_only_response(response_text: str, desired_keywords: int) -> List[str]:
    json_text = extract_json_block(response_text)
    try:
        payload = json.loads(json_text)
        return normalize_keywords(payload.get("keywords", []), desired_keywords)
    except json.JSONDecodeError:
        # Fallback for malformed JSON: recover quoted strings and normalize.
        raw_items = re.findall(r'"((?:[^"\\]|\\.)*)"', json_text)
        decoded = [bytes(item, "utf-8").decode("unicode_escape") for item in raw_items]
        return normalize_keywords(decoded, desired_keywords)


def enrich_keywords(
    image_b64: str,
    model: str,
    ollama_url: str,
    existing_keywords: Sequence[str],
    blacklist_keywords: Sequence[str],
    missing_count: int,
    metadata_summary: str,
    timeout: int,
) -> List[str]:
    if missing_count <= 0:
        return []

    avoid_existing = ", ".join(existing_keywords)
    avoid_blacklist = ", ".join(blacklist_keywords)
    prompt = (
        "You are refining stock-photo keywords. "
        "Return strict JSON only with key: keywords. "
        f"keywords must be an array of exactly {missing_count} concise keywords. "
        "Each keyword must be unique, lowercase-friendly, and 1-3 words. "
        "Prioritize emotional and creative stock keywords (mood, concept, storytelling, atmosphere, symbolic ideas) "
        "that still fit the visible image content. "
        f"Do not include any existing keywords: {avoid_existing}. "
        f"Mandatory blacklist (first pass keywords): {avoid_blacklist}. "
    )
    if metadata_summary:
        prompt += f"Metadata context (optional): {metadata_summary}. "

    body = {
        "model": model,
        "prompt": prompt,
        "format": "json",
        "images": [image_b64],
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 384,
        },
    }
    url = ollama_url.rstrip("/") + "/api/generate"
    for _ in range(2):
        try:
            response = requests.post(url, json=body, timeout=(10, timeout))
            response.raise_for_status()
            data = response.json()
            raw_text = str(data.get("response", ""))
            new_keywords = parse_keywords_only_response(raw_text, missing_count)
            existing_set = set(existing_keywords)
            return [k for k in new_keywords if k not in existing_set][:missing_count]
        except (requests.RequestException, json.JSONDecodeError, ValueError):
            continue
    return []


def enrich_keywords_with_synonyms(
    image_b64: str,
    model: str,
    ollama_url: str,
    existing_keywords: Sequence[str],
    missing_count: int,
    metadata_summary: str,
    timeout: int,
) -> List[str]:
    if missing_count <= 0:
        return []

    existing = ", ".join(existing_keywords)
    prompt = (
        "You are expanding stock-photo keywords with close synonyms and semantically related terms, "
        "plus sensory and descriptive terms grounded in the image. "
        "Return strict JSON only with key: keywords. "
        f"keywords must be an array of exactly {missing_count} concise keywords, 1-3 words each. "
        "Prioritize likely colors, possible ambient sounds, and possible scents suggested by the scene, "
        "plus related descriptive terms useful for stock search. "
        f"Use these existing keywords as context: {existing}. "
        f"Do not repeat any existing keywords: {existing}. "
    )
    if metadata_summary:
        prompt += f"Metadata context (optional): {metadata_summary}. "

    body = {
        "model": model,
        "prompt": prompt,
        "format": "json",
        "images": [image_b64],
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 384,
        },
    }
    url = ollama_url.rstrip("/") + "/api/generate"
    for _ in range(2):
        try:
            response = requests.post(url, json=body, timeout=(10, timeout))
            response.raise_for_status()
            data = response.json()
            raw_text = str(data.get("response", ""))
            new_keywords = parse_keywords_only_response(raw_text, missing_count)
            existing_set = set(existing_keywords)
            return [k for k in new_keywords if k not in existing_set][:missing_count]
        except (requests.RequestException, json.JSONDecodeError, ValueError):
            continue
    return []


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
    analysis_max_side: int,
    timeout: int = 300,
) -> Tuple[str, str, str, str]:
    if requests is None:
        raise FotowordError("Missing dependency 'requests'. Install with: pip install -r requirements.txt")
    analysis_bytes, original_size, analysis_size = build_analysis_image_bytes(image_path, analysis_max_side)
    if original_size and analysis_size and original_size != analysis_size:
        print(
            f"{now_ts()} Analysis resize: {image_path.name} "
            f"{original_size[0]}x{original_size[1]} -> {analysis_size[0]}x{analysis_size[1]}"
        )
    image_b64 = base64.b64encode(analysis_bytes).decode("ascii")

    exif_data = extract_exif(image_path)
    iptc_data = extract_iptc(image_path)
    metadata_summary = summarize_metadata(exif_data, iptc_data)
    first_pass_target = min(10, keyword_count)
    prompt = build_prompt(image_path.name, first_pass_target, metadata_summary)

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
            title, description, keyword_field, category = parse_model_response(raw_text, first_pass_target)
            pass1_raw = [k.strip() for k in keyword_field.split(",") if k.strip()]
            keyword_list = normalize_single_word_keywords(pass1_raw, first_pass_target)
            print(f"{now_ts()} Keywords pass1 ({len(keyword_list)}): {', '.join(keyword_list)}")
            if len(keyword_list) < keyword_count:
                missing = keyword_count - len(keyword_list)
                pass2_extra = enrich_keywords(
                    image_b64=image_b64,
                    model=model,
                    ollama_url=ollama_url,
                    existing_keywords=keyword_list,
                    blacklist_keywords=keyword_list,
                    missing_count=missing,
                    metadata_summary=metadata_summary,
                    timeout=timeout,
                )
                if len(pass2_extra) < 15:
                    pass2_retry = enrich_keywords(
                        image_b64=image_b64,
                        model=model,
                        ollama_url=ollama_url,
                        existing_keywords=keyword_list + pass2_extra,
                        blacklist_keywords=keyword_list,
                        missing_count=missing,
                        metadata_summary=metadata_summary,
                        timeout=timeout,
                    )
                    if pass2_retry:
                        pass2_extra = normalize_keywords(pass2_extra + pass2_retry, missing)
                print(f"{now_ts()} Keywords pass2 ({len(pass2_extra)}): {', '.join(pass2_extra)}")
                merged = normalize_keywords(keyword_list + pass2_extra, keyword_count)
                if len(merged) < keyword_count:
                    missing_after_pass2 = keyword_count - len(merged)
                    pass3_extra = enrich_keywords_with_synonyms(
                        image_b64=image_b64,
                        model=model,
                        ollama_url=ollama_url,
                        existing_keywords=merged,
                        missing_count=missing_after_pass2,
                        metadata_summary=metadata_summary,
                        timeout=timeout,
                    )
                    print(f"{now_ts()} Keywords pass3 ({len(pass3_extra)}): {', '.join(pass3_extra)}")
                    merged = normalize_keywords(merged + pass3_extra, keyword_count)
                else:
                    print(f"{now_ts()} Keywords pass3 (0): skipped (already reached target)")
                if len(merged) < keyword_count:
                    fallback_extra = description_words_fallback(description, merged, keyword_count)
                    print(f"{now_ts()} Keywords fallback from description ({len(fallback_extra)}): {', '.join(fallback_extra)}")
                    if fallback_extra:
                        merged = normalize_keywords(merged + fallback_extra, keyword_count)
                else:
                    print(f"{now_ts()} Keywords fallback from description (0): skipped (already reached target)")
                keyword_field = ", ".join(merged)
                print(f"{now_ts()} Keywords final ({len(merged)}): {', '.join(merged)}")
            else:
                print(f"{now_ts()} Keywords pass2 (0): skipped (already reached target)")
                print(f"{now_ts()} Keywords pass3 (0): skipped (already reached target)")
                print(f"{now_ts()} Keywords final ({len(keyword_list)}): {', '.join(keyword_list)}")
                keyword_field = ", ".join(keyword_list)
            return title, description, keyword_field, category
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
    elif platform_key == "dreamstime":
        # Matches official Dreamstime spreadsheet header schema.
        c1, c2, c3 = infer_dreamstime_categories(title, description, keywords)
        dreamstime_keywords_final = to_dreamstime_keywords(keywords)
        base = {
            "filename": filename,
            "image name": title,
            "description": description,
            "category 1": c1,
            "category 2": c2,
            "category 3": c3,
            "keywords": dreamstime_keywords_final,
            "free": "0",
            "w-el": "0",
            "p-el": "0",
            "sr-el": "0",
            "sr-price": "0",
            "editorial": "0",
            "mr doc ids": "",
            "pr docs": "",
        }
    elif platform_key == "shutterstock":
        base = {
            "filename": filename,
            "description": description,
            "keywords": keywords,
            "categories": infer_shutterstock_categories(title, description, keywords),
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


def open_metadata_writer(out_dir: Path):
    path = metadata_csv_path(out_dir)
    ensure_csv_with_header(path, METADATA_HEADERS)
    fh = path.open("a", newline="", encoding="utf-8")
    writer = csv.DictWriter(fh, fieldnames=METADATA_HEADERS, extrasaction="ignore")
    return fh, writer


def write_platform_csv(path: Path, headers: Sequence[str], rows: Sequence[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(headers), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_metadata_csv(out_dir: Path, metadata_map: Dict[str, Dict[str, str]]) -> None:
    path = metadata_csv_path(out_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=METADATA_HEADERS, extrasaction="ignore")
        writer.writeheader()
        for filename in sorted(metadata_map.keys(), key=lambda s: s.lower()):
            writer.writerow(normalized_metadata_row(filename, metadata_map[filename]))


def run() -> int:
    args = parse_args()

    script_dir = Path(__file__).resolve().parent
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
                title, description, keywords, category = generate_metadata(
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
                }
                processed += 1
                print(f"{now_ts()} Processed: {image_path.name}")
            except Exception as exc:
                failed += 1
                failed_names.add(image_path.name)
                print(f"Failed: {image_path.name} ({exc})", file=sys.stderr)

        # Rebuild platform CSV files from metadata rows (including user-edited agency keywords).
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


if __name__ == "__main__":
    main()
