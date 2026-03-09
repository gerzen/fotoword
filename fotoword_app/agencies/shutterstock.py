from typing import Dict, List, Sequence, Tuple


def infer_shutterstock_categories(title: str, description: str, keywords_field: str) -> str:
    text = f"{title} {description} {keywords_field}".lower()
    rules: List[Tuple[str, Sequence[str]]] = [
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


def shutterstock_row(title: str, description: str, keywords: str) -> Dict[str, str]:
    return {
        "description": description,
        "keywords": keywords,
        "categories": infer_shutterstock_categories(title, description, keywords),
    }
