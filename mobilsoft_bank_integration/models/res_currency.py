# -*- coding: utf-8 -*-

from odoo import fields, models


class CurrencyRate(models.Model):
    _inherit = 'res.currency.rate'

    source = fields.Selection(
        selection=[
            ('manual', 'Manuel'),
            ('garantibbva', 'Garanti BBVA'),
            ('ziraat', 'Ziraat Bankası'),
            ('qnb', 'QNB Finansbank'),
            ('tcmb', 'TCMB'),
        ],
        string='Kaynak',
        default='manual',
    )
    bank_connector_id = fields.Many2one(
        'bank.connector', string='Banka Konektörü',
    )
