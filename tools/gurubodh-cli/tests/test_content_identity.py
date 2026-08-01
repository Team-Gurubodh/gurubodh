import unittest

from gurubodh.content_identity import (
    GURUBODH_CONTENT_NAMESPACE,
    build_content_identity,
    content_key,
    normalize_chapter_content_v1,
)


class ContentIdentityTests(unittest.TestCase):
    def test_normalization_handles_devanagari_line_endings_and_outer_whitespace(self):
        nfd = "\u0928\u093f\u0928\u094d\u0926\u0941\u092a\u093e\u0920"
        normalized = normalize_chapter_content_v1(f" \t{nfd}\r\nअंतर  स्थान\t\rअंत  \n ")
        self.assertEqual(normalized, "निन्दुपाठ\nअंतर  स्थान\nअंत")

    def test_equivalent_normalized_content_has_repeatable_identity(self):
        first = build_content_identity("CAT001", "SUB123", "hi-Deva", "\nज्ञान  \r\nपाठ\t")
        second = build_content_identity("CAT001", "SUB123", "hi-Deva", "ज्ञान  \nपाठ")
        self.assertEqual(first, second)
        self.assertEqual(first["namespace"], str(GURUBODH_CONTENT_NAMESPACE))

    def test_identity_changes_for_internal_text_or_subject_language_identity(self):
        base = build_content_identity("CAT001", "SUB123", "hi-Deva", "ज्ञान पाठ")
        self.assertNotEqual(base["content_key"], build_content_identity("CAT001", "SUB123", "hi-Deva", "ज्ञान-पाठ")["content_key"])
        self.assertNotEqual(base["content_key"], build_content_identity("CAT002", "SUB123", "hi-Deva", "ज्ञान पाठ")["content_key"])
        self.assertNotEqual(base["content_key"], build_content_identity("CAT001", "SUB123", "sa-Deva", "ज्ञान पाठ")["content_key"])

    def test_content_key_rejects_blank_or_noncanonical_checksum(self):
        with self.assertRaisesRegex(ValueError, "non-blank"):
            content_key("", "SUB123", "hi-Deva", "a" * 64)
        with self.assertRaisesRegex(ValueError, "lowercase hexadecimal"):
            content_key("CAT001", "SUB123", "hi-Deva", "A" * 64)


if __name__ == "__main__":
    unittest.main()
