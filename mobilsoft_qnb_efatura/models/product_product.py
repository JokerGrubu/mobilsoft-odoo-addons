# -*- coding: utf-8 -*-
"""
Ürün Modeli Genişletmesi
QNB e-Belge için ürün eşleştirmesi artık Nilvera/UBL ile aynı mantıkta:
Odoo standart product.product._retrieve_product kullanılır (qnb_document_line).
"""

from odoo import models, fields


class ProductProduct(models.Model):
    _inherit = 'product.product'

    external_product_codes = fields.Text(
        string='Diğer Harici Kodlar',
        help='JSON formatında diğer harici sistem kodları: {"system": "code"}'
    )

    # Eşleştirme metadata
    last_matched_source = fields.Selection([
        ('qnb', 'QNB e-Solutions'),
        ('bizimhesap', 'BizimHesap'),
        ('xml', 'XML Import'),
        ('manual', 'Manuel')
    ], string='Son Eşleştirme Kaynağı')

    last_matched_date = fields.Datetime(
        string='Son Eşleştirme Tarihi'
    )
