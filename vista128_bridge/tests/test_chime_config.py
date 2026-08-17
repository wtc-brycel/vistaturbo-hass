import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from vista_bridge.config import _zone_list


class ChimeZoneConfigTests(unittest.TestCase):
    def test_empty_list(self):
        self.assertEqual(_zone_list(""), ())

    def test_numbers_and_ranges(self):
        self.assertEqual(_zone_list("1, 2, 5-8,27"), (1, 2, 5, 6, 7, 8, 27))

    def test_invalid_zone_rejected(self):
        with self.assertRaises(ValueError):
            _zone_list("1,129")

    def test_descending_range_rejected(self):
        with self.assertRaises(ValueError):
            _zone_list("8-5")


if __name__ == "__main__":
    unittest.main()
