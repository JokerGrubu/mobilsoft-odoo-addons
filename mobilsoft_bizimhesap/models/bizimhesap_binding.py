# -*- coding: utf-8 -*-

from odoo import models, fields, api


class BizimHesapPartnerBinding(models.Model):
    """
    BizimHesap - Odoo Partner Eşleştirmesi
    """
    _name = 'bizimhesap.partner.binding'
    _description = 'BizimHesap Partner Binding'
    _inherit = 'bizimhesap.binding'
    _rec_name = 'odoo_id'

    odoo_id = fields.Many2one(
        'res.partner',
        string='Odoo Partner',
        required=True,
        ondelete='cascade',
    )
    
    # BizimHesap'tan gelen ek bilgiler
    external_code = fields.Char(string='BizimHesap Kodu')
    external_balance = fields.Float(string='BizimHesap Bakiye')
    contact_type = fields.Selection([
        ('1', 'Müşteri'),
        ('2', 'Tedarikçi'),
        ('3', 'Her İkisi'),
    ], string='Cari Tipi')


class BizimHesapProductBinding(models.Model):
    """
    BizimHesap - Odoo Product Eşleştirmesi
    """
    _name = 'bizimhesap.product.binding'
    _description = 'BizimHesap Product Binding'
    _inherit = 'bizimhesap.binding'
    _rec_name = 'odoo_id'

    odoo_id = fields.Many2one(
        'product.product',
        string='Odoo Ürün',
        required=True,
        ondelete='cascade',
    )
    
    external_code = fields.Char(string='BizimHesap Kodu')
    external_stock = fields.Float(string='BizimHesap Stok')


class BizimHesapInvoiceBinding(models.Model):
    """
    BizimHesap - Odoo Invoice Eşleştirmesi
    """
    _name = 'bizimhesap.invoice.binding'
    _description = 'BizimHesap Invoice Binding'
    _inherit = 'bizimhesap.binding'
    _rec_name = 'odoo_id'

    odoo_id = fields.Many2one(
        'account.move',
        string='Odoo Fatura',
        required=True,
        ondelete='cascade',
    )
    
    external_number = fields.Char(string='BizimHesap Fatura No')
    invoice_type = fields.Selection([
        ('1', 'Satış Faturası'),
        ('2', 'Alış Faturası'),
    ], string='Fatura Tipi')
