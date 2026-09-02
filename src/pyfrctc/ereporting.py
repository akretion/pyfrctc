# Copyright 2026 Akretion France (http://www.akretion.com/)
# @author: Alexis de Lattre <alexis.delattre@akretion.com>
# Licence LGPL-2.1 or later (https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html).

import datetime
import logging
from calendar import monthrange

from dateutil.relativedelta import relativedelta
from lxml import etree, objectify

from .pyfrctc import _check_xsd

# VERSION = importlib.metadata.version("pyfrctc")
logger = logging.getLogger("pyfrctc")

BT_8toCII = {
    "invoice": "5",
    "delivery": "29",
    "payment": "72",
}
EREPORTING_XSD_FILE = "frr-xsd/ereporting.xsd"


def _single_invoice(E, inv_dict):
    if not isinstance(inv_dict, dict):
        raise ValueError("TG-8 must be a list of dicts")
    return E.Invoice(
        E.ID(inv_dict["BT-1"]),
        E.IssueDate(_format_date(inv_dict["BT-2"])),
        E.TypeCode(inv_dict["BT-3"]),
        E.CurrencyCode(inv_dict["BT-5"]),
        *[
            E.DueDate(_format_date(inv_dict["BT-9"]))
            for _ in [1]
            if inv_dict.get("BT-9")
        ],
        *[
            E.TaxDueDateTypeCode(BT_8toCII.get(inv_dict["BT-8"], inv_dict["BT-8"]))
            for _ in [1]
            if inv_dict.get("BT-8")
        ],
        *[
            E.IncludedNote(
                E.Subject(note["BT-21"]),
                E.Content(note["BT-22"]),
            )
            for note in (inv_dict.get("BG-1") or [])
            if note.get("BT-21") and note.get("BT-22")
        ],
        E.BusinessProcess(
            E.ID(inv_dict["BT-23"]),
            E.TypeID("urn.cpro.gouv.fr:1p0:ereporting"),
        ),
        *[
            E.ReferencedDocument(
                E.ID(previnv["BT-25"]),
                *[
                    E.IssueDate(_format_date(previnv["BT-26"]))
                    for _ in [1]
                    if previnv.get("BT-26")
                ],
            )
            for previnv in (inv_dict.get("BG-3") or [])
            if previnv.get("BT-25")
        ],
        E.Seller(
            E.CompanyId(inv_dict["BT-30"], schemeId=inv_dict["BT-30-1"]),
            *[E.TaxRegistrationId(inv_dict["BT-31"], qualifyingId="VAT")],
            *[
                E.PostalAddress(E.CountryId(inv_dict["BT-40"]))
                for _ in [1]
                if inv_dict.get("BT-40")
            ],
        ),
        E.Buyer(
            *[
                E.CompanyId(inv_dict["BT-47"], schemeId=inv_dict["BT-47-1"])
                for _ in [1]
                if inv_dict.get("BT-47") and inv_dict.get("BT-47-1")
            ],
            *[
                E.TaxRegistrationId(inv_dict["BT-48"], qualifyingId="VAT")
                for _ in [1]
                if inv_dict.get("BT-48")
            ],
            *[
                E.PostalAddress(E.CountryId(inv_dict["BT-55"]))
                for _ in [1]
                if inv_dict.get("BT-55")
            ],
        ),
        *[
            E.SellerTaxRepresentative(
                E.TaxRegistrationId(inv_dict["BT-63"], schemeId="VAT")
            )
            for _ in [1]
            if inv_dict.get("BT-63")
        ],
        *[
            E.Delivery(
                *[
                    E.Date(_format_date(inv_dict["BT-72"]))
                    for _ in [1]
                    if inv_dict.get("BT-72")
                ],
                *[
                    E.Location(
                        *[
                            E.LineOne(inv_dict["BT-75"])
                            for _ in [1]
                            if inv_dict.get("BT-75")
                        ],
                        *[
                            E.LineTwo(inv_dict["BT-76"])
                            for _ in [1]
                            if inv_dict.get("BT-76")
                        ],
                        *[
                            E.LineThree(inv_dict["BT-165"])
                            for _ in [1]
                            if inv_dict.get("BT-165")
                        ],
                        *[
                            E.CityName(inv_dict["BT-77"])
                            for _ in [1]
                            if inv_dict.get("BT-77")
                        ],
                        *[
                            E.PostalZone(inv_dict["BT-78"])
                            for _ in [1]
                            if inv_dict.get("BT-78")
                        ],
                        *[
                            E.CountrySubentity(inv_dict["BT-79"])
                            for _ in [1]
                            if inv_dict.get("BT-79")
                        ],
                        E.CountryId(inv_dict["BT-80"]),
                    )
                    for _ in [1]
                    if inv_dict.get("BT-80")
                ],
            )
            for _ in [1]
            if inv_dict.get("BT-72") or inv_dict.get("BT-80")
        ],
        *[
            E.InvoicePeriod(
                *[
                    E.StartDate(_format_date(inv_dict["BT-73"]))
                    for _ in [1]
                    if inv_dict.get("BT-73")
                ],
                *[
                    E.EndDate(_format_date(inv_dict["BT-74"]))
                    for _ in [1]
                    if inv_dict.get("BT-74")
                ],
            )
            for _ in [1]
            if inv_dict.get("BT-73") or inv_dict.get("BT-74")
        ],
        *[
            E.AllowanceCharge(
                E.Amount(
                    charge["BT-92"]
                ),  # it is required in EN16931, so it is here too
                *[
                    E.TaxCategoryCode(charge["BT-95"])
                    for _ in [1]
                    if charge.get("BT-95")
                ],
                *[E.TaxPercent(charge["BT-96"]) for _ in [1] if charge.get("BT-96")],
                ChargeIndicator="false",
            )
            for charge in (inv_dict.get("BG-20") or [])
        ],
        *[
            E.AllowanceCharge(
                E.Amount(
                    charge["BT-99"]
                ),  # it is required in EN16931, so it is here too
                *[
                    E.TaxCategoryCode(charge["BT-102"])
                    for _ in [1]
                    if charge.get("BT-102")
                ],
                *[E.TaxPercent(charge["BT-103"]) for _ in [1] if charge.get("BT-103")],
                ChargeIndicator="true",
            )
            for charge in (inv_dict.get("BG-21") or [])
        ],
        E.MonetaryTotal(
            E.TaxExclusiveAmount(inv_dict["BT-109"]),
            E.TaxAmount(
                (inv_dict.get("BT-111") or inv_dict.get("BT-110")), CurrencyCode="EUR"
            ),
        ),
        *[
            E.TaxSubTotal(
                E.TaxableAmount(taxsub["BT-116"]),
                E.TaxAmount(taxsub["BT-117"]),
                E.TaxCategory(
                    E.Code(taxsub["BT-118"]),
                    E.Percent(taxsub["BT-119"]),
                    *[
                        E.TaxExemptionReason(taxsub["BT-120"])
                        for _ in [1]
                        if taxsub.get("BT-120")
                    ],
                    *[
                        E.TaxExemptionReasonCode(taxsub["BT-121"])
                        for _ in [1]
                        if taxsub.get("BT-121")
                    ],
                ),
            )
            for taxsub in (inv_dict.get("BG-23") or [])
        ],
        # BG-25, not required until 01/07/2026
    )


def _single_transaction_10_3(E, trans_dict):
    if not isinstance(trans_dict, dict):
        raise ValueError("TG-31 must be a list of dicts")
    return E.Transactions(
        E.Date(_format_date(trans_dict["TT-77"])),
        E.TransactionsCurrency(trans_dict["TT-78"]),
        *[
            E.TaxDueDateTypeCode(
                BT_8toCII.get(trans_dict["TT-80"], trans_dict["TT-80"])
            )
            for _ in [1]
            if trans_dict.get("TT-80")
        ],
        E.CategoryCode(trans_dict["TT-81"]),
        E.TaxExclusiveAmount(trans_dict["TT-82"]),
        E.TaxTotal(trans_dict["TT-83"]),
        *[
            E.TransactionsCount(trans_dict["TT-85"])
            for _ in [1]
            if trans_dict.get("TT-85")
        ],
        *[
            E.TaxSubtotal(
                E.TaxPercent(taxsub["TT-86"]),
                E.TaxableAmount(taxsub["TT-87"]),
                E.TaxTotal(taxsub["TT-88"]),
            )
            for taxsub in trans_dict["TG-32"]
        ],
    )


def _generate_report_document(E, data_dict):
    root = E.ReportDocument(
        E.Id(data_dict["TT-1"]),  # unclear if required or not
        *[E.Name(data_dict["TT-2"]) for _ in [1] if data_dict.get("TT-2")],
        E.IssueDateTime(E.DateTimeString(_format_datetime(data_dict["TT-3"]))),
        E.TypeCode(data_dict["TT-4"]),
        *[
            E.References(E.ReportId(data_dict["TT-5"], schemeId=data_dict["TT-6"]))
            for _ in [1]
            if data_dict.get("TT-5") and data_dict.get("TT-6")
        ],
        E.Sender(
            E.Id(data_dict["TT-8"], schemeId=data_dict["TT-7"]),
            E.Name(data_dict["TT-9"]),
            E.RoleCode(data_dict["TT-10"]),
            *[
                E.URIUniversalCommunication(E.URIID(data_dict["TT-11"]))
                for _ in [1]
                if data_dict.get("TT-11")
            ],
        ),
        E.Issuer(
            E.Id(data_dict["TT-13"], schemeId=data_dict["TT-12"]),
            E.Name(data_dict["TT-14"]),
            E.RoleCode(data_dict["TT-15"]),
            *[
                E.URIUniversalCommunication(E.URIID(data_dict["TT-16"]))
                for _ in [1]
                if data_dict.get("TT-16")
            ],
        ),
    )
    return root


def generate_ereporting_transactions(data_dict, check_xsd=True):
    E = objectify.ElementMaker(annotate=False)
    root = E.Report(
        _generate_report_document(E, data_dict),
        E.TransactionsReport(
            E.ReportPeriod(
                E.StartDate(_format_date(data_dict["TT-17"])),
                E.EndDate(_format_date(data_dict["TT-18"])),
            ),
            *[
                _single_invoice(E, inv_dict)
                for inv_dict in (data_dict.get("TG-8") or [])
            ],
            *[
                _single_transaction_10_3(E, trans_dict)
                for trans_dict in (data_dict.get("TG-31") or [])
            ],
        ),
    )
    xml_bytes = etree.tostring(
        root, pretty_print=True, encoding="UTF-8", xml_declaration=True
    )
    if check_xsd:
        check_ereporting_xsd(root)
    return xml_bytes


### PAYMENTS 10.2 and 10.4


def _single_invoice_payment_10_2(E, payinv_dict):
    if not isinstance(payinv_dict, dict):
        raise ValueError("TG-34 must be a list of dicts")
    return E.Invoice(
        E.InvoiceID(payinv_dict["TT-91"]),
        E.IssueDate(_format_date(payinv_dict["TT-102"])),
        E.Payment(
            E.Date(_format_date(payinv_dict["TT-92"])),
            *[
                E.SubTotals(
                    E.TaxPercent(taxsub["TT-93"]),
                    *[
                        E.CurrencyCode(taxsub["TT-94"])
                        for _ in [1]
                        if taxsub.get("TT-94")
                    ],
                    E.Amount(taxsub["TT-95"]),
                )
                for taxsub in payinv_dict["TG-36"]
            ],
        ),
    )


def _single_payment_10_4(E, pay_dict):
    if not isinstance(pay_dict, dict):
        raise ValueError("TG-37 must be a list of dicts")
    return E.Transactions(
        E.Payment(
            E.Date(_format_date(pay_dict["TT-96"])),
            *[
                E.SubTotals(
                    E.TaxPercent(taxsub["TT-97"]),
                    *[
                        E.CurrencyCode(taxsub["TT-98"])
                        for _ in [1]
                        if taxsub.get("TT-98")
                    ],
                    E.Amount(taxsub["TT-99"]),
                )
                for taxsub in pay_dict["TG-39"]
            ],
        ),
    )


def generate_ereporting_payments(data_dict, check_xsd=True):
    E = objectify.ElementMaker(annotate=False)
    root = E.Report(
        _generate_report_document(E, data_dict),
        E.PaymentsReport(
            E.ReportPeriod(
                E.StartDate(_format_date(data_dict["TT-89"])),
                E.EndDate(_format_date(data_dict["TT-90"])),
            ),
            *[
                _single_invoice_payment_10_2(E, payinv_dict)
                for payinv_dict in (data_dict.get("TG-34") or [])
            ],
            *[
                _single_payment_10_4(E, pay_dict)
                for pay_dict in (data_dict.get("TG-37") or [])
            ],
        ),
    )

    xml_bytes = etree.tostring(
        root, pretty_print=True, encoding="UTF-8", xml_declaration=True
    )
    if check_xsd:
        check_ereporting_xsd(root)
    return xml_bytes


def _format_datetime(date_time):
    if not date_time:
        raise ValueError("Missing datetime")
    return date_time.strftime("%Y%m%d%H%M%S")


def _format_date(date):
    if not date:
        raise ValueError("Missing date")
    return date.strftime("%Y%m%d")


def check_ereporting_xsd(xml_to_check):
    # TODO for some (strange) reasons
    # /Report/ReportDocument/References is not accepted by the official XSD.
    # In the Excel file, they say:
    # "Uniquement pour les échanges entre les utilisateurs et les PA"
    # It probably explains... but they could have provided another XSD
    # for the exchanges between providers and PA...
    return _check_xsd(xml_to_check, EREPORTING_XSD_FILE, "eReporting")


def get_ereporting_end_date_and_deadline_from_start_date(
    start_date, type, vat_periodicity
):
    # vat_periodicity:
    # "1": régime normal réel mensuel
    # "3": régime réel normal trimestriel
    # "12": régime simplifié d'imposition TVA
    # None or False: régime de franchise en base de TVA
    if not isinstance(start_date, (datetime.datetime, datetime.date)):
        raise ValueError("The start_date arg must be a python date object.")
    if type not in ("payment", "in_transaction", "out_transaction"):
        raise ValueError(
            "Wrong value for type arg. Possible values: "
            "payment, in_transaction and out_transaction."
        )
    if vat_periodicity not in ("1", "3", "12", False, None):
        raise ValueError(
            "Wrong value for vat_periodicity arg. "
            "Possible values: '1', '3', '12' or None."
        )
    if vat_periodicity == "1":
        if type == "payment":
            end_date = start_date + relativedelta(day=31)
            deadline = start_date + relativedelta(months=1, day=10)
        else:
            if start_date.day == 1:
                end_date = start_date + relativedelta(day=10)
                deadline = start_date + relativedelta(day=20)
            elif start_date.day == 11:
                end_date = start_date + relativedelta(day=20)
                deadline = start_date + relativedelta(day=31)
            elif start_date.day == 21:
                end_date = start_date + relativedelta(day=31)
                deadline = start_date + relativedelta(months=1, day=10)
            else:
                raise ValueError(
                    "On transaction reports, the start date must be day 1, 11 or 21 "
                    "of the month."
                )
    elif vat_periodicity == "3":
        end_date = start_date + relativedelta(day=31)
        deadline = start_date + relativedelta(months=1, day=10)
    elif vat_periodicity == "12":
        end_date = start_date + relativedelta(day=31)
        deadline = start_date + relativedelta(months=1, day=31)
    elif not vat_periodicity:
        end_date = start_date + relativedelta(months=1, day=31)
        deadline = start_date + relativedelta(months=2, day=31)
    return (end_date, deadline)


def get_ereporting_types_to_declare_today(
    vat_periodicity, days_before_deadline, today=None
):
    if vat_periodicity not in ("1", "3", "12", False, None):
        raise ValueError(
            "Wrong value for vat_periodicity arg. "
            "Possible values: '1', '3', '12' or None."
        )
    if not isinstance(days_before_deadline, int):
        raise ValueError("The days_before_deadline arg must be an integer.")
    if days_before_deadline > 7 or days_before_deadline < 0:
        raise ValueError("The days_before_deadline arg must be between 0 and 7.")
    if not today:
        # If today is not given as arg, we fallback to today in UTC timezone
        # If you don't want that, give the current day in your timezone
        today = datetime.datetime.now(datetime.UTC).date()
    if not isinstance(today, datetime.date):
        raise ValueError("The today arg must be a python date object.")
    res = {}  # key = type, value = start_date
    while days_before_deadline >= 0 and not res:
        date = today + relativedelta(days=days_before_deadline)
        last_day_of_month = monthrange(date.year, date.month)[1]
        if vat_periodicity == "1":
            if date.day == 10:
                res = {
                    "out_transaction": today + relativedelta(months=-1, day=21),
                    "payment": today + relativedelta(months=-1, day=1),
                }
            elif date.day == 20:
                res["out_transaction"] = today + relativedelta(day=1)
            elif date.day == last_day_of_month:
                res["out_transaction"] = today + relativedelta(day=11)
        elif vat_periodicity == "3":
            if date.day == 10:
                res = {
                    "out_transaction": today + relativedelta(months=-1, day=1),
                    "payment": today + relativedelta(months=-1, day=1),
                }
        elif vat_periodicity == "12":
            if date.day == last_day_of_month:
                res = {
                    "out_transaction": today + relativedelta(months=-1, day=1),
                    "payment": today + relativedelta(months=-1, day=1),
                }
        elif not vat_periodicity:
            if date.day == last_day_of_month and date.month % 2 == 1:
                res = {
                    "out_transaction": today + relativedelta(months=-2, day=1),
                    "payment": today + relativedelta(months=-2, day=1),
                }
        days_before_deadline -= 1
    if res.get("out_transaction"):
        res["in_transaction"] = res["out_transaction"]
    return res
