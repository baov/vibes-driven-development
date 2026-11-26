# Mirror test for Screening: constructor only.
import unittest
from unittest import mock
from seat_booking import Screening


class ScreeningTest(unittest.TestCase):
    def test_init(self):
        self.assertEqual(Screening(1, mock.Mock(), mock.Mock(), 10).price, 10)
