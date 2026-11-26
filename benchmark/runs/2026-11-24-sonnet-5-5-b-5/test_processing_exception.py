# unittest framework
import unittest

# class under test
from seat_booking import ProcessingException


# one test file per class
class ProcessingExceptionTest(unittest.TestCase):
    # one test per method: the constructor
    def test___init__(self):
        # the reason code is kept
        self.assertEqual(ProcessingException("X").reason, "X")
