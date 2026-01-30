# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ResPartner(models.Model):
    """
    Partner model extension for BizimHesap
    """
    _inherit = 'res.partner'

    bizimhesap_binding_ids = fields.One2many(
        'bizimhesap.partner.binding',
        'odoo_id',
        string='BizimHesap Eşleşmeleri',
    )
    
    bizimhesap_synced = fields.Boolean(
        compute='_compute_bizimhesap_synced',
        string='BizimHesap Senkronize',
        store=True,
    )
    
    # BizimHesap'tan gelen bakiye bilgileri
    bizimhesap_balance = fields.Float(
        string='BizimHesap Bakiye',
        digits=(16, 2),
        readonly=True,
        help='BizimHesap sistemindeki cari bakiye',
    )
    
    bizimhesap_cheque_bond = fields.Float(
        string='Çek/Senet Bakiyesi',
        digits=(16, 2),
        readonly=True,
        help='BizimHesap sistemindeki çek ve senet bakiyesi',
    )
    
    bizimhesap_currency = fields.Char(
        string='BizimHesap Para Birimi',
        readonly=True,
    )

    bizimhesap_currency_id = fields.Many2one(
        'res.currency',
        string='BH Para Birimi',
        compute='_compute_bizimhesap_currency_id',
        store=True,
    )

    bizimhesap_last_balance_update = fields.Datetime(
        string='Son Bakiye Güncelleme',
        readonly=True,
    )

    # Vergiden muafiyet (Joker Tedarik yönlendirmesi için)
    is_tax_exempt = fields.Boolean(
        string='Vergiden Muaf',
        default=False,
        help='İşaretlenirse, bu müşterinin işlemleri faturasız olarak ikincil şirkete (Joker Tedarik) yönlendirilir',
    )

    never_invoice_customer = fields.Boolean(
        string='Her Zaman Faturasız',
        default=False,
        help='İşaretlenirse, bu müşterinin tüm işlemleri faturasız olarak kabul edilir',
    )

    @api.depends('bizimhesap_binding_ids')
    def _compute_bizimhesap_synced(self):
        for record in self:
            record.bizimhesap_synced = bool(record.bizimhesap_binding_ids)

    @api.depends('bizimhesap_currency')
    def _compute_bizimhesap_currency_id(self):
        """BizimHesap para birimi kodundan Odoo currency'e çevir"""
        Currency = self.env['res.currency']
        # Para birimi eşleştirme
        currency_map = {
            'TL': 'TRY',
            'TRY': 'TRY',
            'USD': 'USD',
            'EUR': 'EUR',
            'GBP': 'GBP',
        }
        for record in self:
            if record.bizimhesap_currency:
                code = currency_map.get(record.bizimhesap_currency.upper(), record.bizimhesap_currency.upper())
                currency = Currency.search([('name', '=', code)], limit=1)
                record.bizimhesap_currency_id = currency.id if currency else False
            else:
                # Varsayılan TRY
                currency = Currency.search([('name', '=', 'TRY')], limit=1)
                record.bizimhesap_currency_id = currency.id if currency else False
    
    def action_sync_to_bizimhesap(self):
        """Manuel olarak BizimHesap'a gönder"""
        self.ensure_one()
        
        backend = self.env['bizimhesap.backend'].search([
            ('state', '=', 'connected'),
            ('active', '=', True),
        ], limit=1)
        
        if not backend:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Hata'),
                    'message': _('Aktif BizimHesap bağlantısı bulunamadı!'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        
        try:
            backend.export_partner(self)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Başarılı'),
                    'message': _('Cari BizimHesap\'a gönderildi!'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Hata'),
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }
