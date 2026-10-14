# Copyright 2026 Akretion France (https://www.akretion.com).
# @author: Alexis de Lattre <alexis.delattre@akretion.com>

import unittest
from datetime import date, datetime

from pyfrctc import (
    generate_ereporting_payments,
    generate_ereporting_transactions,
    get_ereporting_end_date_and_deadline_from_start_date,
    get_ereporting_types_to_declare_today,
)

DATE_FMT = "%Y-%m-%d"


class TestGenerateEreporting(unittest.TestCase):
    def _prepare_invoice_dict(self):
        inv_dict = {
            "BT-1": "F124212",
            "BT-2": date(2026, 6, 17),
            "BT-3": "380",
            "BT-5": "EUR",
            "BT-8": "invoice",
            "BT-9": date(2026, 8, 16),
            "BT-10": "120943",
            "BT-11": "Projet_Zorro",
            "BT-12": "Contrat_du_siècle",
            "BT-13": "PO1242",
            "BT-14": "DEVIS2093",
            "BT-15": "BR-2026/06/42",
            "BT-16": "BL-2026/05/12",
            "BT-19": "401HOF",
            "BT-20": "30 jours net",
            "BT-23": "S1",
            "BT-24": "urn.cpro.gouv.fr:1p0:ereporting",  # to generate
            "BG-4": {  # Seller
                "name": "Au bon moulin",
                "biz_name": "L'huile d'olive en folie",
                "identifiers": {
                    # key = schemeID, value = GlobalID value
                    # if not key: value = ID
                    # None: 'REF_SELLER',  # not allowed by UBL schematron
                    "0009": "99999999800019",
                    "0224": "Code_ROUTAGE_seller",
                },
                "legal_identifier": "999999998",
                "legal_identifier_schemeid": "0002",
                "legal_info": "SARL au capital de 42 000 € - APE 6201Z",
                "vat_identifier": "FR11999999998",
                "tax_identifier": "DGFIP_ref_1242",
                "einvoicing_addr": "999999998_042",
                "einvoicing_addr_schemeid": "0225",
                "addr_l1": "1242 chemin de l'olive",
                "addr_l2": "Lieu dit des senteurs",
                "addr_l3": "ZAC du Mont Ventoux",
                "city": "Malaucène",
                "postcode": "84340",
                "country_subdivision": "Vaucluse",
                "country_code": "FR",
                "contacts": [
                    {
                        "name": "M. Rémi Dupont",
                        "phone": "+33 6 12 42 12 42",
                        "email": "commercial@aubonmoulin.com",
                    }
                ],
            },
            "BG-7": {  # Buyer
                "name": "Ma jolie boutique SARL",
                "biz_name": "Ma jolie Trading Brand",
                "identifiers": {
                    # for buyer: either ID (key None) or GlobalID, not both
                    #                None: "REF_BUYER",
                    "0009": "78787878400018",
                    # FX schematron doesn't allow multiple schemes for buyer
                    # but it allows that for seller... I don't understand this !
                    #                "0224": 'code_routage_buyer',
                },
                "legal_identifier": "787878784",
                "legal_identifier_schemeid": "0002",
                "vat_identifier": "FR19787878784",
                "einvoicing_addr": "787878784",
                "einvoicing_addr_schemeid": "0225",
                "addr_l1": "35 rue de la République",
                "addr_l2": "La presqu'île",
                "city": "Lyon",
                "postcode": "69001",
                "country_subdivision": "Rhône",
                "country_code": "FR",
                # either personName (BT-56) OR DepartmentName (BT-56-0), not both
                "contacts": [
                    {
                        "name": "Mme Laëtitia Durand",
                        "phone": "+33 7 42 12 42 12",
                        "email": "laetita.durand@jolieboutique.com",
                    }
                ],
            },
            "BG-13": {  # Ship to
                "name": "Plateforme logistique FastIT",
                "identifiers": {
                    "0009": "63636363200010",
                },
                "country_code": "FR",
                "city": "Carpentras",
                "postcode": "84200",
                "addr_l1": "5 avenue Georges Clémenceau",
                "addr_l2": "ZAC du lac vert",
            },
            "BT-72": date(2026, 6, 14),
            "BG-1": [
                {
                    "BT-21": "AAI",
                    "BT-22": "Ceci est une information générale",
                },
                {
                    "BT-21": "ADN",
                    "BT-22": "B2G",
                },
                {"BT-22": "note sans sujet !"},
                {
                    "BT-21": "PMT",
                    "BT-22": "Indemnité forfaitaire pour frais de recouvrement "
                    "en cas de retard de paiement : 40 €.",
                },
                {
                    "BT-21": "PMD",
                    "BT-22": "Tout retard de paiement engendre une pénalité "
                    "exigible à compter de la date d'échéance, "
                    "calculée sur la base de trois fois le taux d'intérêt légal.",
                },
                {
                    "BT-21": "AAB",
                    "BT-22": "Les réglements reçus avant la date d'échéance "
                    "ne donneront pas lieu à escompte.",
                },
            ],
            "BG-23": [
                {
                    "BT-117": "27.6",
                    "BT-116": "138.00",
                    "BT-118": "S",
                    "BT-119": "20.00",
                },
                {
                    "BT-117": "7.43",
                    "BT-116": "135.00",
                    "BT-118": "S",
                    "BT-119": "5.50",
                },
            ],
            "BT-106": "273.00",
            "BT-107": "5.50",
            "BT-108": "5.50",
            "BT-109": "273.00",
            "BT-111": "35.03",
            "BT-111-1": "EUR",
            "BT-112": "308.03",
            "BT-113": "100.00",
            "BT-115": "208.03",
            "BG-3": [
                {
                    "BT-25": "F124211",
                    "EXT-FR-FE-02": "386",
                    "BT-26": date(2025, 12, 30),
                },
                {
                    "BT-25": "F124210",
                    #     'BT-26': datetime.strptime("2025-09-01", DATE_FMT),
                },
            ],
            "BT-17": "LOT12",
            "BT-18-00": {  # key = BT-18-1: value = BT-18
                "AHK": "EMPL042",
                "AHO": "Chamber0823",
            },
            "BG-24": [
                {
                    "BT-122": "JUSTIF42",
                    "BT-123": "DOCUMENT_ANNEXE",  # allowed codes in BR-FR-17
                    "BT-124": "https://www.share.com/justif42.pdf",
                },
                {
                    "BT-122": "JUSTIF43",
                    "BT-123": "BON_LIVRAISON",
                    "BT-124": "https://www.share.com/justif43.pdf",
                },
            ],
            "BG-20": [
                {
                    "amount": "3.00",
                    "base_amount": "138.00",
                    "reason": "Consigne",
                    "vat_category_code": "S",
                    "vat_rate": "20.00",
                },
                {
                    "amount": "2.50",
                    "base_amount": "138.00",
                    "reason": "Réduc fidélité",
                    "vat_category_code": "S",
                    "vat_rate": "20.00",
                },
            ],
            "BG-21": [
                {
                    "amount": "5.50",
                    "base_amount": "138.00",
                    "reason": "Surtaxe carburant",
                    "vat_category_code": "S",
                    "vat_rate": "20.00",
                }
            ],
            "BG-25": [  # Invoice lines
                {
                    "BT-126": "1",
                    "BT-127": "Olives récoltées exclusivement dans le Vaucluse (FR)",
                    "BT-155": "JOIO50CL",
                    "BT-153": "Huile d'olive Joio 50cl",
                    "BT-157": "3518370900150",
                    "BT-157-1": "0160",
                    "BT-159": "FR",
                    "BT-146": "13.50",
                    "BT-147": "1.50",
                    "BT-148": "15.00",
                    "BT-129": "10",
                    "BT-130": "C62",
                    "BT-133": "623400",
                    "BT-151": "S",
                    "BT-152": "5.50",
                    "BT-131": "135.00",  # Total HT
                    "BT-134": date(2026, 6, 14),
                    "BT-135": date(2026, 6, 15),
                    "BG-32": {  # key = BT-160: value = BT-161
                        "Couleur": "Vert",
                        "Taille": "L",
                    },
                    "BT-158-00": {  # key = (BT-158-1, BT-158-2): value = BT-158
                        ("BB", "1.0"): "LOT1242",
                        ("HS", "NC8"): "15092000",
                    },
                    "BG-27": [
                        {
                            "BT-136": "1.50",
                            "BT-139": "test",
                        },
                    ],
                    "BG-28": [
                        {
                            "BT-141": "1.50",
                            "BT-144": "test inverse",
                        },
                    ],
                },
                {
                    "BT-126": "2",
                    "BT-127": "Nougat préparé par les moines et les "
                    "moniales du Barroux (FR)",
                    "BT-155": "NOUGATCUBES",
                    "BT-153": "Nougats en cubes",
                    "BT-157": "3518370400049",
                    "BT-157-1": "0160",
                    "BT-159": "FR",
                    "BT-146": "6.90",
                    "BT-147": "1.05",
                    "BT-148": "7.95",
                    "BT-128-00": {  # key = BT-128-1: value = BT-128
                        "MWB": "AWB129871",
                    },
                    "BT-129": "20",
                    "BT-130": "C62",
                    "BT-133": "623400",
                    "BT-151": "S",
                    "BT-152": "20.00",
                    "BT-131": "138.00",  # Total HT
                    "BT-132": "DV843873",
                    "EXT-FR-FE-135": "PO982749",
                    "EXT-FR-FE-140": "BL0982432",
                    "EXT-FR-FE-141": "AVIS9074398",
                    # EXT-FR-FE-BG-10
                    "EXT-FR-FE-149": "Alpes du Sud Logistique",
                    "EXT-FR-FE-155": "05600",
                    "EXT-FR-FE-151": "12 rue de Vanban",
                    "EXT-FR-FE-154": "Eygliers",
                    "EXT-FR-FE-157": "FR",
                    # ref to previous invoice
                    "EXT-FR-FE-136": "F824739",
                    "EXT-FR-FE-139": "12",
                    "EXT-FR-FE-137": "380",
                    "EXT-FR-FE-138": date(2025, 12, 24),
                },
            ],
        }
        return inv_dict

    def _prepare_document(self):
        datetime_fmt = "%Y-%m-%d %H:%M:%S"
        data_dict = {
            "TT-1": "IDentifier",
            "TT-2": "ID Name",
            "TT-3": datetime.strptime("2026-07-03 21:35:42", datetime_fmt),
            #            "TT-4": "RE",
            "TT-4": "IN",
            #            "TT-5": "IDprevious",
            #            "TT-6": "IN",
            # Sender TG-3
            "TT-8": "0111",  # Matricule of SUPER PDP
            "TT-7": "0238",
            "TT-9": "SUPER PDP",
            "TT-10": "WK",
            "TT-11": "853322915",
            # Issuer TG-5
            "TT-13": "792377731",
            "TT-12": "0002",
            "TT-14": "Akretion France",
            "TT-15": "SE",
            "TT-16": "792377731",
        }
        return data_dict

    def _prepare_transactions(self):
        data_dict = self._prepare_document()
        data_dict.update(
            {
                "TT-17": date(2026, 8, 1),
                "TT-18": date(2026, 8, 10),
                # List of invoices
                "TG-8": [
                    self._prepare_invoice_dict(),
                ],
                "TG-31": [
                    {
                        "TT-77": date(2026, 8, 1),
                        "TT-78": "EUR",
                        "TT-80": "invoice",
                        "TT-81": "TLB1",
                        "TT-82": "1500.00",
                        "TT-83": "227.50",
                        "TG-32": [
                            {
                                "TT-86": "20.00",
                                "TT-87": "1000.00",
                                "TT-88": "200.00",
                            },
                            {
                                "TT-86": "5.50",
                                "TT-87": "500.00",
                                "TT-88": "27.50",
                            },
                        ],
                    },
                ],
            }
        )
        return data_dict

    def _prepare_payments(self):
        data_dict = self._prepare_document()
        data_dict.update(
            {
                "TT-89": date(2026, 8, 1),
                "TT-90": date(2026, 8, 10),
                "TG-34": [
                    {
                        "TT-91": "F2026-005",
                        "TT-102": date(2026, 6, 25),
                        "TT-92": date(2026, 8, 3),
                        "TG-36": [
                            {
                                "TT-93": "20.00",
                                "TT-94": "EUR",
                                "TT-95": "983.43",
                            },
                            {
                                "TT-93": "5.50",
                                "TT-94": "EUR",
                                "TT-95": "876.44",
                            },
                        ],
                    },
                    {
                        "TT-91": "F2026-012",
                        "TT-102": date(2026, 7, 2),
                        "TT-92": date(2026, 8, 4),
                        "TG-36": [
                            {
                                "TT-93": "20.00",
                                "TT-94": "EUR",
                                "TT-95": "55.66",
                            },
                            {
                                "TT-93": "5.50",
                                "TT-94": "EUR",
                                "TT-95": "42.42",
                            },
                        ],
                    },
                ],
                "TG-37": [
                    {
                        "TT-96": date(2026, 8, 1),
                        "TG-39": [
                            {
                                "TT-97": "20.00",
                                "TT-98": "EUR",
                                "TT-99": "234.99",
                            },
                            {
                                "TT-97": "5.50",
                                "TT-98": "EUR",
                                "TT-99": "456.78",
                            },
                        ],
                    },
                    {
                        "TT-96": date(2026, 8, 2),
                        "TG-39": [
                            {
                                "TT-97": "20.00",
                                "TT-98": "EUR",
                                "TT-99": "909.55",
                            },
                            {
                                "TT-97": "5.50",
                                "TT-98": "EUR",
                                "TT-99": "789.12",
                            },
                        ],
                    },
                ],
            }
        )
        return data_dict

    def test_generate_ereporting_transactions(self):
        data_dict = self._prepare_transactions()
        _xml_bytes = generate_ereporting_transactions(data_dict)

    def test_generate_ereporting_payments(self):
        data_dict = self._prepare_payments()
        _xml_bytes = generate_ereporting_payments(data_dict)

    def test_get_end_date_and_deadline_from_start_date(self):
        in2out = {
            (date(2026, 9, 1), "payment", "1"): (date(2026, 9, 30), date(2026, 10, 10)),
            (date(2026, 9, 1), "out_transaction", "1"): (
                date(2026, 9, 10),
                date(2026, 9, 20),
            ),
            (date(2026, 9, 11), "out_transaction", "1"): (
                date(2026, 9, 20),
                date(2026, 9, 30),
            ),
            (date(2026, 9, 21), "out_transaction", "1"): (
                date(2026, 9, 30),
                date(2026, 10, 10),
            ),
            (date(2026, 9, 1), "out_transaction", "3"): (
                date(2026, 9, 30),
                date(2026, 10, 10),
            ),
            (date(2026, 9, 1), "payment", "3"): (date(2026, 9, 30), date(2026, 10, 10)),
            (date(2026, 9, 1), "out_transaction", "12"): (
                date(2026, 9, 30),
                date(2026, 10, 31),
            ),
            (date(2026, 9, 1), "payment", "12"): (
                date(2026, 9, 30),
                date(2026, 10, 31),
            ),
            (date(2026, 9, 1), "out_transaction", None): (
                date(2026, 10, 31),
                date(2026, 11, 30),
            ),
            (date(2026, 9, 1), "payment", None): (
                date(2026, 10, 31),
                date(2026, 11, 30),
            ),
        }
        for method_args, res in in2out.items():
            result = get_ereporting_end_date_and_deadline_from_start_date(*method_args)
            self.assertEqual(res, result)

    def test_get_types_to_declare_today(self):
        in2out = {
            ("1", 2, date(2026, 9, 6)): {},
            ("1", 0, date(2026, 9, 20)): {"out_transaction": date(2026, 9, 1)},
            ("1", 2, date(2026, 9, 18)): {"out_transaction": date(2026, 9, 1)},
            ("1", 2, date(2026, 9, 19)): {"out_transaction": date(2026, 9, 1)},
            ("1", 2, date(2026, 9, 20)): {"out_transaction": date(2026, 9, 1)},
            ("1", 0, date(2026, 9, 30)): {"out_transaction": date(2026, 9, 11)},
            ("1", 0, date(2026, 9, 10)): {
                "out_transaction": date(2026, 8, 21),
                "payment": date(2026, 8, 1),
            },
            ("3", 0, date(2026, 9, 10)): {
                "out_transaction": date(2026, 8, 1),
                "payment": date(2026, 8, 1),
            },
            ("3", 5, date(2026, 9, 20)): {},
            ("12", 0, date(2026, 9, 30)): {
                "out_transaction": date(2026, 8, 1),
                "payment": date(2026, 8, 1),
            },
            ("12", 6, date(2026, 9, 12)): {},
            (None, 0, date(2026, 9, 30)): {
                "out_transaction": date(2026, 7, 1),
                "payment": date(2026, 7, 1),
            },
            (None, 3, date(2026, 10, 15)): {},
            (None, 0, date(2026, 10, 31)): {},
        }
        for method_args, res in in2out.items():
            result = get_ereporting_types_to_declare_today(*method_args)
            self.assertEqual(result.get("out_transaction"), res.get("out_transaction"))
            self.assertEqual(result.get("payment"), res.get("payment"))
            self.assertEqual(
                result.get("out_transaction"), result.get("in_transaction")
            )
