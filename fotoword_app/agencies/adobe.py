from typing import Dict

ADOBE_CATEGORIES: Dict[int, str] = {
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


def infer_adobe_category(title: str, description: str, keywords_field: str) -> str:
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


def adobe_row(filename: str, description: str, keywords: str, category: str) -> Dict[str, str]:
    return {
        "filename": filename,
        "title": description,
        "keywords": keywords,
        "category": category,
    }
