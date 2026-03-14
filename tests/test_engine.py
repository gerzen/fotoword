import unittest
from unittest.mock import patch

from fotoword_app.engine import (
    DESCRIPTION_LIMIT,
    build_editorial_description,
    build_prompt,
    format_editorial_date,
    infer_usage_purpose,
    platform_row,
    short_description_for_export,
    split_description_variants,
)


class EngineBehaviorTests(unittest.TestCase):
    def test_infer_usage_purpose_from_filename_suffix(self) -> None:
        self.assertEqual(infer_usage_purpose("photo_CO.jpg"), "commercial")
        self.assertEqual(infer_usage_purpose("photo_ED.jpg"), "editorial")
        self.assertEqual(infer_usage_purpose("photo.jpg"), "commercial")

    def test_split_description_variants_preserves_removed_tail(self) -> None:
        text = (
            "A detailed commercial stock description with multiple clauses, carrying extra context, "
            "ending with a useful trailing phrase"
        )

        full_description, short_description = split_description_variants(text, limit=90)

        self.assertEqual(
            short_description,
            "A detailed commercial stock description with multiple clauses, carrying extra context.",
        )
        self.assertEqual(
            full_description,
            "A detailed commercial stock description with multiple clauses, carrying extra context. "
            "(ending with a useful trailing phrase)",
        )
        self.assertEqual(short_description_for_export(full_description), short_description)

    def test_format_editorial_date_uses_expected_template_spacing(self) -> None:
        formatted = format_editorial_date({"DateTimeOriginal": "2026:02:28 17:35:23"}, {})
        self.assertEqual(formatted, "February 28, 2026")

    def test_build_editorial_description_uses_metadata_template(self) -> None:
        description = build_editorial_description(
            filename="scene_ED.jpg",
            generated_title="Generated fallback title",
            raw_description="Crowds gather in a public square during a city event",
            exif_data={"DateTimeOriginal": "2026:02:28 17:35:23"},
            iptc_data={
                "iptc_city": "Berlin",
                "iptc_country": "Germany",
                "iptc_title": "Demonstrators gather at central square",
            },
        )

        self.assertEqual(
            description,
            "Berlin, Germany - February 28, 2026. Demonstrators gather at central square. "
            "Crowds gather in a public square during a city event.",
        )

    def test_build_editorial_description_falls_back_to_placeholders_and_logs_warnings(self) -> None:
        with patch("fotoword_app.engine.print") as mock_print:
            description = build_editorial_description(
                filename="scene_ED.jpg",
                generated_title="Generated title",
                raw_description="People watch the event from behind safety barriers",
                exif_data={},
                iptc_data={},
            )

        self.assertEqual(
            description,
            "City, Country - Month DD, YYYY. Generated title. "
            "People watch the event from behind safety barriers.",
        )
        logged_messages = " ".join(str(call.args[0]) for call in mock_print.call_args_list)
        self.assertIn("missing IPTC city", logged_messages)
        self.assertIn("missing IPTC country", logged_messages)
        self.assertIn("missing or unreadable capture date", logged_messages)

    def test_build_prompt_uses_remaining_editorial_character_budget(self) -> None:
        prompt = build_prompt("scene_ED.jpg", 10, "IPTC: iptc_city: Berlin", 123)
        self.assertIn("no longer than 123 characters", prompt)
        self.assertIn("Do not repeat city, country, date, or IPTC title text", prompt)

    def test_platform_row_sets_editorial_flags_per_agency(self) -> None:
        dreamstime_row = platform_row(
            platform="dreamstime",
            filename="scene_ED.jpg",
            headers=["Filename", "Image Name", "Description", "Editorial"],
            title="Scene title",
            description="Scene description.",
            keywords="crowd, city",
            category="11",
        )
        shutterstock_row = platform_row(
            platform="shutterstock",
            filename="scene_ED.jpg",
            headers=["Filename", "Description", "Keywords", "Categories", "Editorial"],
            title="Scene title",
            description="Scene description.",
            keywords="crowd, city",
            category="11",
        )
        adobe_row = platform_row(
            platform="adobe",
            filename="scene_ED.jpg",
            headers=["Filename", "Title", "Keywords", "Category"],
            title="Scene title",
            description="Scene description.",
            keywords="crowd, city",
            category="11",
        )

        self.assertEqual(dreamstime_row["Editorial"], "1")
        self.assertEqual(shutterstock_row["Editorial"], "yes")
        self.assertNotIn("Editorial", adobe_row)

    def test_editorial_description_respects_character_limit(self) -> None:
        long_raw_description = "word " * 400

        description = build_editorial_description(
            filename="scene_ED.jpg",
            generated_title="Generated fallback title",
            raw_description=long_raw_description,
            exif_data={"DateTimeOriginal": "2026:02:28 17:35:23"},
            iptc_data={
                "iptc_city": "Berlin",
                "iptc_country": "Germany",
                "iptc_title": "Demonstrators gather at central square",
            },
            limit=DESCRIPTION_LIMIT,
        )

        self.assertLessEqual(len(description), DESCRIPTION_LIMIT)


if __name__ == "__main__":
    unittest.main()
