# -*- coding: utf-8 -*-

from odoo import fields, models


class CurrencyRate(models.Model):
    """Extend currency rate with bank source tracking"""

    _inherit = "res.currency.rate"

    source = fields.Selection(
        selection=[
            ("manual", "Manual"),
            ("garantibbva", "Garanti BBVA"),
            ("ziraat", "Ziraat Bank"),
            ("tcmb", "TCMB (Central Bank)"),
        ],
        string="Rate Source",
        default="manual",
        help="Source of this exchange rate",
    )
    bank_connector_id = fields.Many2one(
        "bank.connector.abstract",
        string="Bank Connector",
        help="Bank connector that provided this rate",
    )


class Currency(models.Model):
    """Extend currency with auto-update settings"""

    _inherit = "res.currency"

    auto_update_from_bank = fields.Boolean(
        string="Auto Update from Bank",
        help="Automatically update exchange rates from connected banks",
    )
    preferred_bank = fields.Selection(
        [
            ("garantibbva", "Garanti BBVA"),
            ("ziraat", "Ziraat Bank"),
            ("tcmb", "TCMB"),
        ],
        string="Preferred Bank",
        help="Preferred bank for exchange rate updates",
    )
