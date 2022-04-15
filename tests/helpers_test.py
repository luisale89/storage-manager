import unittest
from app.utils.helpers import (
    _epoch_utc_to_datetime, normalize_string, 
)

class Normalize_names_tests(unittest.TestCase):

    def test1_valid_input(self):
        v = normalize_string('lUiS')
        self.assertEqual(v, "Luis")

    