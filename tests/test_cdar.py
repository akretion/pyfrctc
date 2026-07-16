# Copyright 2026 Akretion France (https://www.akretion.com).
# @author: Alexis de Lattre <alexis.delattre@akretion.com>

import datetime
import unittest

from pyfrctc import generate_cdar, parse_cdar


class TestGenerateEreporting(unittest.TestCase):
    def _prepare_dispute_cdar_dict(self):
        cdar_dict = {
            "MDT-100": datetime.date(2026, 7, 13),
            "MDT-105": "207",
            "MDT-106": "Disputed",
            "MDT-129": {"0002": "000000002"},
            "MDT-2": "REGULATED",
            "MDT-21": "BY",
            "MDT-3": "urn.cpro.gouv.fr:1p0:CDV:invoice",
            "MDT-38": {"0002": "000000001"},
            "MDT-39": "Tricatel",
            "MDT-4": "INV/2026/0092_380_2026-07-13#207_20260716111054",
            "MDT-40": "BY",
            "MDT-57": {"0002": "000000002"},
            "MDT-58": "Burger Queen",
            "MDT-59": "SE",
            "MDT-73": "315143296_3829",
            "MDT-73-1": "0225",
            "MDT-74": False,
            "MDT-77": 23,
            "MDT-78": datetime.datetime(2026, 7, 16, 11, 10, 54),
            "MDT-8": datetime.datetime(2026, 7, 16, 11, 10, 54),
            "MDT-87": "INV/2026/0092",
            "MDT-88": "46",
            "MDT-91": "380",
            "MDT-95": datetime.datetime(2026, 7, 13, 13, 56, 22),
            "MDG-37": [
                {
                    "MDT-113": "QUALITE_ERR",
                    "MDT-114": "Qualité d'article livré incorrecte",
                    "MDT-121": "CNP",
                    "MDT-122": "Créer un Avoir Partiel",
                    "MDT-126": "Ca fuit de partout... tout est inondé !",
                },
                {
                    "MDT-113": "TX_TVA_ERR",
                    "MDT-114": "Taux de TVA erroné",
                    "MDT-121": "NIN",
                    "MDT-122": "Créer une Facture Rectificative",
                    "MDT-126": "TVA 10% et non 20% (attestation signée)",
                },
            ],
        }
        return cdar_dict

    def test_generate_dispute_cdar(self):
        cdar_dict = self._prepare_dispute_cdar_dict()
        xml_bytes = generate_cdar(cdar_dict)
        _cdar_dict_parsed = parse_cdar(xml_bytes)
