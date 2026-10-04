import unittest

from app.services.bamini_input import decode_bamini_if_present


class BaminiInputTests(unittest.TestCase):
    def test_decodes_legacy_bamini_text(self):
        self.assertEqual(
            decode_bamini_if_present("jpz;Lf;fy; khtl;l", "Bamini"),
            "திண்டுக்கல் மாவட்ட",
        )

    def test_leaves_unicode_tamil_unchanged(self):
        text = "தமிழ்நாடு அரசு"
        self.assertEqual(decode_bamini_if_present(text, "Bamini"), text)

    def test_does_not_convert_ordinary_english_without_bamini_markers(self):
        text = "This is a regular English sentence."
        self.assertEqual(decode_bamini_if_present(text), text)


if __name__ == "__main__":
    unittest.main()
