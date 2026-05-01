from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    vkn = fields.Char(string='VKN', size=10)
    tckn = fields.Char(string='TCKN', size=11)
    iban = fields.Char(string='IBAN')
    is_efatura_user = fields.Boolean(string='e-Fatura Kullanıcısı', default=False)
    efatura_alias = fields.Char(string='e-Fatura Alias')
    partner_status = fields.Selection([
        ('active', 'Aktif'),
        ('passive', 'Pasif'),
        ('blocked', 'Bloke'),
    ], string='Durum', default='active')
    total_receivable = fields.Monetary(
        string='Alacak Bakiyesi',
        currency_field='currency_id',
        compute='_compute_partner_balances',
        store=True,
    )
    total_payable = fields.Monetary(
        string='Borç Bakiyesi',
        currency_field='currency_id',
        compute='_compute_partner_balances',
        store=True,
    )
    net_balance = fields.Monetary(
        string='Net Bakiye',
        currency_field='currency_id',
        compute='_compute_partner_balances',
        store=True,
    )

    @api.depends('credit', 'debit')
    def _compute_partner_balances(self):
        for partner in self:
            partner.total_receivable = partner.credit
            partner.total_payable = partner.debit
            partner.net_balance = partner.credit - partner.debit
