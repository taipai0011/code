import unittest

import app


class TestAppHelpers(unittest.TestCase):
    def test_detect_platform_youtube(self):
        self.assertEqual(app.detect_platform('https://youtube.com/watch?v=abc'), 'YouTube')

    def test_detect_platform_kling(self):
        self.assertEqual(app.detect_platform('https://kling.ai/some/video'), 'Kling AI')

    def test_detect_platform_unknown(self):
        self.assertEqual(app.detect_platform('https://example.com/video'), 'Unknown')

    def test_url_validation(self):
        self.assertTrue(app.is_valid_http_url('https://youtube.com/watch?v=abc'))
        self.assertFalse(app.is_valid_http_url('ftp://youtube.com/watch?v=abc'))
        self.assertFalse(app.is_valid_http_url('not-a-url'))


if __name__ == '__main__':
    unittest.main()
