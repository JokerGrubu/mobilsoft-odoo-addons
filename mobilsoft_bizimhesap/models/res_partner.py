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

    # ═══════════════════════════════════════════════════════════════
    # HESAP HAREKETLERİ - Odoo Fatura ve Ödemeler
    # ═══════════════════════════════════════════════════════════════

    # Fatura özet bilgileri
    bizimhesap_invoice_count = fields.Integer(
        compute='_compute_bizimhesap_account_info',
        string='Fatura Sayısı',
    )
    bizimhesap_invoice_residual = fields.Monetary(
        compute='_compute_bizimhesap_account_info',
        string='Ödenmemiş Tutar',
        currency_field='currency_id',
    )

    # Satış / Alış ayrımı
    bizimhesap_sale_count = fields.Integer(
        compute='_compute_bizimhesap_account_info',
        string='Satış Fatura Sayısı',
    )
    bizimhesap_sale_total = fields.Monetary(
        compute='_compute_bizimhesap_account_info',
        string='Toplam Satış',
        currency_field='currency_id',
    )
    bizimhesap_purchase_count = fields.Integer(
        compute='_compute_bizimhesap_account_info',
        string='Alış Fatura Sayısı',
    )
    bizimhesap_purchase_total = fields.Monetary(
        compute='_compute_bizimhesap_account_info',
        string='Toplam Alış',
        currency_field='currency_id',
    )

    # Ödeme bilgileri
    bizimhesap_payment_count = fields.Integer(
        compute='_compute_bizimhesap_account_info',
        string='Ödeme Sayısı',
    )
    bizimhesap_payment_total = fields.Monetary(
        compute='_compute_bizimhesap_account_info',
        string='Toplam Tahsilat',
        currency_field='currency_id',
    )

    # Odoo bakiye (alacak - borç)
    bizimhesap_odoo_balance = fields.Monetary(
        compute='_compute_bizimhesap_account_info',
        string='Odoo Bakiye',
        currency_field='currency_id',
        help='Odoo sistemindeki cari bakiye (Alacak - Borç)',
    )

    def _compute_bizimhesap_account_info(self):
        """Odoo'daki fatura ve ödeme bilgilerini hesapla"""
        AccountMove = self.env['account.move']

        for partner in self:
            # Satış faturaları (out_invoice)
            sale_invoices = AccountMove.search([
                ('partner_id', '=', partner.id),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
            ])
            partner.bizimhesap_sale_count = len(sale_invoices)
            partner.bizimhesap_sale_total = sum(sale_invoices.mapped('amount_total'))

            # Alış faturaları (in_invoice)
            purchase_invoices = AccountMove.search([
                ('partner_id', '=', partner.id),
                ('move_type', '=', 'in_invoice'),
                ('state', '=', 'posted'),
            ])
            partner.bizimhesap_purchase_count = len(purchase_invoices)
            partner.bizimhesap_purchase_total = sum(purchase_invoices.mapped('amount_total'))

            # Toplam fatura sayısı
            partner.bizimhesap_invoice_count = partner.bizimhesap_sale_count + partner.bizimhesap_purchase_count

            # Ödenmemiş tutar
            all_invoices = sale_invoices | purchase_invoices
            partner.bizimhesap_invoice_residual = sum(all_invoices.mapped('amount_residual'))

            # Ödemeler (tahsilatlar)
            payments = self.env['account.payment'].search([
                ('partner_id', '=', partner.id),
                ('state', '=', 'posted'),
            ])
            partner.bizimhesap_payment_count = len(payments)
            partner.bizimhesap_payment_total = sum(payments.mapped('amount'))

            # Odoo bakiye hesapla (basit: satış - alış)
            # Pozitif = müşteri bize borçlu, Negatif = biz müşteriye borçluyuz
            partner.bizimhesap_odoo_balance = (
                partner.bizimhesap_sale_total -
                partner.bizimhesap_purchase_total -
                partner.bizimhesap_payment_total +
                partner.bizimhesap_invoice_residual
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

    def action_view_bizimhesap_invoices(self):
        """Partner'ın tüm faturalarını görüntüle"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Faturalar - %s') % self.name,
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [
                ('partner_id', '=', self.id),
                ('move_type', 'in', ['out_invoice', 'out_refund', 'in_invoice', 'in_refund']),
                ('state', '=', 'posted'),
            ],
            'context': {'default_partner_id': self.id},
        }

    def action_view_bizimhesap_sale_invoices(self):
        """Partner'ın satış faturalarını görüntüle"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Satış Faturaları - %s') % self.name,
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [
                ('partner_id', '=', self.id),
                ('move_type', 'in', ['out_invoice', 'out_refund']),
                ('state', '=', 'posted'),
            ],
            'context': {'default_partner_id': self.id, 'default_move_type': 'out_invoice'},
        }

    def action_view_bizimhesap_purchase_invoices(self):
        """Partner'ın alış faturalarını görüntüle"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Alış Faturaları - %s') % self.name,
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [
                ('partner_id', '=', self.id),
                ('move_type', 'in', ['in_invoice', 'in_refund']),
                ('state', '=', 'posted'),
            ],
            'context': {'default_partner_id': self.id, 'default_move_type': 'in_invoice'},
        }

    def action_view_bizimhesap_payments(self):
        """Partner'ın ödemelerini görüntüle"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Ödemeler - %s') % self.name,
            'res_model': 'account.payment',
            'view_mode': 'list,form',
            'domain': [
                ('partner_id', '=', self.id),
                ('state', '=', 'posted'),
            ],
            'context': {'default_partner_id': self.id},
        }
