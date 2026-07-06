import pathlib
import unittest


class WashFilterMotionTests(unittest.TestCase):
    def test_wash_crop_does_not_use_visible_dynamic_offsets(self):
        combined_source = (
            pathlib.Path("video_processor.py").read_text(encoding="utf-8")
            + "\n"
            + pathlib.Path("video_splitter.py").read_text(encoding="utf-8")
        )

        self.assertNotIn("sin(t*2)", combined_source)
        self.assertNotIn("cos(t*2)", combined_source)
        self.assertIn("x='trunc((iw-ow)/2)'", combined_source)
        self.assertIn("y='trunc((ih-oh)/2)'", combined_source)


if __name__ == "__main__":
    unittest.main()
