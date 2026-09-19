"""Formatters must never raise, whatever number reaches them.

A crash here takes down the whole render, which is exactly what happened when
a zero cost multiplier produced `inf * 0 = nan`.
"""

import math
import unittest

from pclengine import fmt

AWKWARD = [
    0.0, -0.0, 1.0, -1.0, 0.5, 999.0, 1000.0, 1e6, 1e15, 1e55, 1e308,
    -1e55, 1e-9, float("inf"), float("-inf"), float("nan"),
]
FORMATTERS = [fmt.big, fmt.small, fmt.size, fmt.money, fmt.rate]


class TestFormatters(unittest.TestCase):
    def test_never_raises(self):
        for function in FORMATTERS:
            for value in AWKWARD:
                with self.subTest(fn=function.__name__, value=value):
                    result = function(value)
                    self.assertIsInstance(result, str)
                    self.assertTrue(result, "formatters must return something")

    def test_nan_is_marked_not_printed(self):
        for function in FORMATTERS:
            with self.subTest(fn=function.__name__):
                self.assertNotIn("nan", function(float("nan")).lower())

    def test_infinity_is_marked_not_printed(self):
        for function in (fmt.small, fmt.size, fmt.money):
            for value in (float("inf"), float("-inf")):
                with self.subTest(fn=function.__name__, value=value):
                    self.assertNotIn("inf", function(value).lower())

    def test_readable_magnitudes(self):
        self.assertEqual(fmt.big(1234), "1,234")
        self.assertEqual(fmt.big(1_500_000), "1.500 million")
        self.assertEqual(fmt.small(4200), "4.2k")
        self.assertEqual(fmt.size(750), "750 B")
        self.assertEqual(fmt.size(26000), "26.0 KB")
        self.assertEqual(fmt.money(12.5), "$12.50")
        self.assertEqual(fmt.dur(3661), "1:01:01")

    def test_big_covers_the_whole_range(self):
        """The endgame total has to have a name, not an exponent."""
        self.assertIn("septendecillion", fmt.big(3e55))
        self.assertNotIn("e+", fmt.big(1e54))


if __name__ == "__main__":
    unittest.main()
