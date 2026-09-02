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
            "BT-2": datetime.strptime("2026-06-17", DATE_FMT),
            "BT-3": "380",
            "BT-5": "EUR",
            #            'BT-6': "EUR",
            # for BT-8, as the values are different in UBL and CII
            # we use a codification: 'invoice', 'delivery' or 'payment'
            "BT-8": "invoice",
            "BT-9": datetime.strptime("2026-07-16", DATE_FMT),
            "BT-10": "120943",
            "BT-11": "Projet_Zorro",
            "BT-11-0": "Zorro super projet",
            "BT-12": "Contrat_du_siècle",
            "BT-13": "PO1242",
            "BT-14": "DEVIS2093",
            "BT-15": "BR-2026/06/42",
            "BT-16": "BL-2026/05/12",
            "BT-19": "401HOF",
            "BT-20": "30 jours net",
            "BT-23": "S1",
            "BT-24": "urn.cpro.gouv.fr:1p0:ereporting",  # to generate
            # START Seller BG-4
            "BT-27": "Au bon moulin",
            "BT-28": "L'huile d'olive en folie",
            "BT-29": {
                # key = schemeID, value = GlobalID value
                # if not key: value = ID
                #                None: 'REF_SELLER',
                "0009": "99999999800019",
                "0224": "Code_ROUTAGE_seller",
            },
            "BT-30": "999999998",
            "BT-30-1": "0002",
            "BT-31": "FR11999999998",
            "BT-32": "DGFIP_ref_1242",
            "BT-34": "999999998_042",
            "BT-34-1": "0225",
            "BT-35": "1242 chemin de l'olive",
            "BT-36": "Lieu dit des senteurs",
            "BT-162": "ZAC du Mont Ventoux",
            "BT-37": "Malaucène",
            "BT-38": "84340",
            "BT-39": "Vaucluse",
            "BT-40": "FR",
            "BT-41": "M. Rémi Dupont",
            "BT-42": "+33 6 12 42 12 42",
            "BT-43": "commercial@aubonmoulin.com",
            # START Buyer  BG-7
            "BT-44": "Ma jolie boutique SARL",
            "BT-45": "Ma jolie Trading Brand",
            "BT-46": {
                # for buyer: either ID (key None) or GlobalID, not both
                #                None: "REF_BUYER",
                "0009": "78787878400018",
                # TODO FX schematron doesn't allow multiple schemes for buyer
                # but it allows that for seller... I don't understand this !
                #                "0224": 'code_routage_buyer',
            },
            "BT-47": "787878784",
            "BT-47-1": "0002",
            "BT-48": "FR19787878784",
            "BT-49": "787878784",
            "BT-49-1": "0225",
            "BT-50": "35 rue de la République",
            "BT-51": "La presqu'île",
            "BT-52": "Lyon",
            "BT-53": "69001",
            "BT-54": "Rhône",
            "BT-55": "FR",
            # either personName (BT-56) OR DepartmentName (BT-56-0), not both
            "BT-56": "Mme Laëtitia Durand",
            "BT-57": "+33 7 42 12 42 12",
            "BT-58": "laetita.durand@jolieboutique.com",
            # End Buyer
            # Seller Agent  EXT-FR-FE-BG-03
            "EXT-FR-FE-66": "M. Rémi Agent",
            "EXT-FR-FE-86": "Rémi Agent",
            "EXT-FR-FE-87": "+33 7 87 32 34 54",
            "EXT-FR-FE-88": "remi@superagent.com",
            # Buyer Agent  EXT-FR-FE-BG-01
            "EXT-FR-FE-03": "M. Négociateur CHEF",
            "EXT-FR-FE-23": "Charlotte Dupont",
            "EXT-FR-FE-24": "+33 7 88 55 33 22",
            "EXT-FR-FE-25": "charlotte@supernegociatrice.eu",
            # Invoicer EXT-FR-FE-BG-05
            "EXT-FR-FE-112": "Facturier SARL",
            "EXT-FR-FE-130": "FR",
            "EXT-FR-FE-128": "97400",
            "EXT-FR-FE-127": "St Denis",
            "EXT-FR-FE-124": "12 rue Sainte Marie",
            "EXT-FR-FE-117": "704721240",
            "EXT-FR-FE-118": "0002",
            # Invoicee EXT-FR-FE-BG-04
            "EXT-FR-FE-89": "Receipee EURL",
            "EXT-FR-FE-107": "FR",
            "EXT-FR-FE-105": "69001",
            "EXT-FR-FE-104": "Lyon",
            "EXT-FR-FE-101": "42 boulevard de la Croix Rousse",
            "EXT-FR-FE-94": "528010523",
            "EXT-FR-FE-95": "0002",
            # Start Tax Representative
            "BT-62": "Société écran",
            "BT-69": "FR",
            "BT-63": "FR15123456789",
            "BT-73": datetime.strptime("2026-06-01", DATE_FMT),
            "BT-74": datetime.strptime("2026-06-30", DATE_FMT),
            # Start Ship to
            "BT-70": "Plateforme logistique FastIT",
            "BT-71": {
                "0009": "63636363200010",
            },
            "BT-80": "FR",
            "BT-77": "Carpentras",
            "BT-78": "84200",
            "BT-75": "5 avenue Georges Clémenceau",
            "BT-76": "ZAC du Venoux",
            "BT-165": "Bâtiment A",
            "BT-72": datetime.strptime("2026-06-14", DATE_FMT),
            "BT-83": datetime.strptime("2026-06-17", DATE_FMT),
            "BT-81": "30",
            "BT-82": "Libellé du moyen de paiement",
            #            "BT-87": "567890",
            #            "BT-88": "Alexis de Lattre",
            "BT-84": "FR2012421242124212421242124",
            "BT-85": "Au bon moulin SARL",
            "BT-86": "QNTOFRP1XXX",
            "BT-89": "RUM_9083209",
            # Payeur EXT-FR-FE-BG-02
            "EXT-FR-FE-43": "Société payeur",
            "EXT-FR-FE-61": "FR",
            "EXT-FR-FE-59": "05100",
            "EXT-FR-FE-58": "Névache",
            "EXT-FR-FE-55": "Vallée étroite",
            "EXT-FR-FE-52": "754760932",
            "EXT-FR-FE-53": "0225",
            "EXT-FR-FE-48": "754760932",
            "EXT-FR-FE-49": "0002",
            "BT-91": "FR7312345678901275089715A98",
            "BT-90": "Au bon moulin SARL",
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
                    "BT-117-1": "EUR",  # TODO
                    "BT-116": "138.00",
                    "BT-116-1": "EUR",  # TODO
                    "BT-118": "S",
                    "BT-119": "20.00",
                },
                {
                    "BT-117": "7.43",
                    "BT-117-1": "EUR",  # TODO
                    "BT-116": "135.00",
                    "BT-116-1": "EUR",  # TODO
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
                    "BT-26": datetime.strptime("2025-12-30", DATE_FMT),
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
                    "BT-92": "3.00",
                    "BT-93": "138.00",
                    "BT-97": "Consigne",
                    "BT-95": "S",
                    "BT-96": "20.00",
                },
                {
                    "BT-92": "2.50",
                    "BT-93": "138.00",
                    "BT-97": "Réduc fidélité",
                    "BT-95": "S",
                    "BT-96": "20.00",
                },
            ],
            "BG-21": [
                {
                    "BT-99": "5.50",
                    "BT-100": "138.00",
                    "BT-104": "Surtaxe carburant",
                    "BT-102": "S",
                    "BT-103": "20.00",
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
                    "BT-134": datetime.strptime("2026-06-14", DATE_FMT),
                    "BT-135": datetime.strptime("2026-06-15", DATE_FMT),
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
                    "EXT-FR-FE-138": datetime.strptime("2025-12-24", DATE_FMT),
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
                "TT-17": datetime.strptime("2026-08-01", DATE_FMT),
                "TT-18": datetime.strptime("2026-08-10", DATE_FMT),
                # List of invoices
                "TG-8": [
                    self._prepare_invoice_dict(),
                ],
                "TG-31": [
                    {
                        "TT-77": datetime.strptime("2026-08-01", DATE_FMT),
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
                "TT-89": datetime.strptime("2026-08-01", DATE_FMT),
                "TT-90": datetime.strptime("2026-08-10", DATE_FMT),
                "TG-34": [
                    {
                        "TT-91": "F2026-005",
                        "TT-102": datetime.strptime("2026-06-25", DATE_FMT),
                        "TT-92": datetime.strptime("2026-08-03", DATE_FMT),
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
                        "TT-102": datetime.strptime("2026-07-02", DATE_FMT),
                        "TT-92": datetime.strptime("2026-08-04", DATE_FMT),
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
                        "TT-96": datetime.strptime("2026-08-01", DATE_FMT),
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
                        "TT-96": datetime.strptime("2026-08-02", DATE_FMT),
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
