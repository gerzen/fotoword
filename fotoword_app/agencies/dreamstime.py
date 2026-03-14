import re
from typing import Dict, List, Sequence, Tuple

from fotoword_app.constants import DREAMSTIME_CATEGORY_RULES, DREAMSTIME_MAX_KEYWORDS


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
        matches = ["145"]
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


def dreamstime_row(title: str, description: str, keywords: str, editorial: str) -> Dict[str, str]:
    c1, c2, c3 = infer_dreamstime_categories(title, description, keywords)
    return {
        "image name": title,
        "description": description,
        "category 1": c1,
        "category 2": c2,
        "category 3": c3,
        "keywords": to_dreamstime_keywords(keywords),
        "free": "0",
        "w-el": "0",
        "p-el": "0",
        "sr-el": "0",
        "sr-price": "0",
        "editorial": editorial,
        "mr doc ids": "",
        "pr docs": "",
    }
