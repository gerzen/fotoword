import unittest
from unittest.mock import patch

from fotoword_app.engine import (
    ADOBE_TITLE_LIMIT,
    DESCRIPTION_LIMIT,
    adobe_title_for_export,
    build_editorial_description,
    build_prompt,
    finalize_description,
    format_editorial_date,
    infer_usage_purpose,
    parse_model_response,
    platform_row,
    short_description_for_export,
    split_description_variants,
)


class EngineBehaviorTests(unittest.TestCase):
    def test_infer_usage_purpose_from_filename_suffix(self) -> None:
        self.assertEqual(infer_usage_purpose("photo_CO.jpg"), "commercial")
        self.assertEqual(infer_usage_purpose("photo_ED.jpg"), "editorial")
        self.assertEqual(infer_usage_purpose("photo.jpg"), "commercial")

    def test_infer_usage_purpose_from_metadata_keywords_when_filename_is_neutral(self) -> None:
        self.assertEqual(infer_usage_purpose("photo.jpg", "nature, editorial, berlin"), "editorial")
        self.assertEqual(infer_usage_purpose("photo.jpg", "nature, commercial, stock"), "commercial")
        self.assertEqual(infer_usage_purpose("photo.jpg", "nature, editorial, commercial"), "commercial")
        self.assertEqual(infer_usage_purpose("photo.jpg", "nature, city"), "commercial")

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
        prompt = build_prompt("scene_ED.jpg", 10, "IPTC: iptc_city: Berlin", 123, "editorial")
        self.assertIn("no longer than 123 characters", prompt)
        self.assertIn("Do not repeat city, country, date, or IPTC title text", prompt)

    def test_finalize_description_uses_resolved_editorial_purpose_for_neutral_filename(self) -> None:
        description = finalize_description(
            filename="20260307-152547-DSC_6381_ST.jpg",
            title="Wall with Stickers",
            raw_description="Street wall covered with stickers near a posted restriction sign",
            keywords_field="berlin, editorial, stickers",
            exif_data={},
            iptc_data={
                "iptc_title": "Wall Covered with Stickers and Photo and Video Restriction Sign.",
                "iptc_keywords": "Berlin, editorial, modern art",
                "iptc_date_created": "20260307",
            },
            purpose="editorial",
        )

        self.assertEqual(
            description,
            "City, Country - March 07, 2026. Wall Covered with Stickers and Photo and Video Restriction Sign. "
            "Street wall covered with stickers near a posted restriction sign.",
        )

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
        self.assertEqual(adobe_row["Title"], "Scene description.")

    def test_adobe_title_for_export_truncates_at_last_period_or_comma_within_limit(self) -> None:
        description = (
            "A very long stock description sentence that keeps building context for the Adobe export title. "
            "It adds another clause with city details and weather notes and scene atmosphere and architectural context "
            "and pedestrian movement and reflective surfaces and soft light beyond the allowed Adobe title length."
        )

        adobe_title = adobe_title_for_export(description)

        self.assertLessEqual(len(adobe_title), ADOBE_TITLE_LIMIT)
        self.assertEqual(
            adobe_title,
            "A very long stock description sentence that keeps building context for the Adobe export title.",
        )

    def test_parse_model_response_raises_clear_error_when_keywords_are_missing(self) -> None:
        response = '{"title":"Street art scene","description":"Urban wall with layered posters","category":11}'

        with self.assertRaisesRegex(ValueError, "failed to generate keywords"):
            parse_model_response(response, 5)

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
