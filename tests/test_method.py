# Copyright 2026 Akretion (https://www.akretion.com).
# @author Sébastien BEAU <sebastien.beau@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import unittest

from pyfrctc import get_directory_siren


class TestAPI(unittest.TestCase):
    def test_get_directory_siren(self):
        with self.assertRaises(ValueError):
            get_directory_siren(None, None)
