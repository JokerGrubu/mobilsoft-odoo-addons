# -*- coding: utf-8 -*-

from odoo import fields, models


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    bank_connector_id = fields.Many2one(
        'bank.connector', string='Banka Konektörü',
        help='Bu hesabı yöneten banka bağlantısı',
    )
    bank_external_account_id = fields.Char(
        string='Harici Hesap ID',
        help='Banka API tarafından verilen hesap tanımlayıcı',
        index=True,
    )
    last_sync = fields.Datetime(string='Son Senkronizasyon', readonly=True)
