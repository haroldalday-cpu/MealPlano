"""Milestone 6 tests: input rules from PRD Section 12."""

import unittest

from mealplano.validation import (InputError, check_password, check_username, clean_name,
                                  format_pesos, parse_pesos)


class ParsePesosTests(unittest.TestCase):
    def test_valid_amounts(self):
        cases = {"80": 8000, "80.5": 8050, "80.50": 8050, "0.01": 1, "1,200": 120000,
                 "₱80": 8000, "P35.25": 3525, " 100000.00 ": 10_000_000, "80.10": 8010,
                 "0000080": 8000}
        for text, centavos in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_pesos(text), centavos)

    def test_invalid_amounts(self):
        for text in ["", "   ", "abc", "80.505", "-5", "0", "0.00", "100000.01", "1e3",
                     "12.3.4", ".50", None, "1000000", "9" * 5000]:
            with self.subTest(text=text):
                with self.assertRaises(InputError):
                    parse_pesos(text)

    def test_format(self):
        self.assertEqual(format_pesos(11575), "₱115.75")
        self.assertEqual(format_pesos(1), "₱0.01")
        self.assertEqual(format_pesos(10_000_000), "₱100,000.00")
        self.assertEqual(format_pesos(-500), "-₱5.00")


class NameAndAccountRules(unittest.TestCase):
    def test_food_name(self):
        self.assertEqual(clean_name("  Adobo  "), "Adobo")
        self.assertEqual(clean_name("x" * 50), "x" * 50)
        for bad in ["", "   ", None, "x" * 51]:
            with self.subTest(name=bad):
                with self.assertRaises(InputError):
                    clean_name(bad)

    def test_username(self):
        self.assertEqual(check_username(" harold_09 "), "harold_09")
        for bad in ["ab", "a" * 31, "has space", "semi;colon", ""]:
            with self.subTest(username=bad):
                with self.assertRaises(InputError):
                    check_username(bad)

    def test_password_length_boundaries(self):
        self.assertEqual(check_password("12345678"), "12345678")     # exactly 8: allowed
        with self.assertRaises(InputError):
            check_password("1234567")                                 # 7: rejected
        with self.assertRaises(InputError):
            check_password("x" * 129)


if __name__ == "__main__":
    unittest.main()
