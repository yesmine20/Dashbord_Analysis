import unittest

from src.pdf_report import _inline_markup, markdown_to_pdf


class TestPdfReport(unittest.TestCase):
    def test_normalizes_nonbreaking_punctuation(self):
        markdown = "period\u202fJuly\u00a02020\u2011margin"
        self.assertEqual(_inline_markup(markdown), "period July 2020-margin")
        self.assertTrue(markdown_to_pdf(markdown).startswith(b"%PDF-"))


if __name__ == "__main__":
    unittest.main()
