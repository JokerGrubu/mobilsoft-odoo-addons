# -*- coding: utf-8 -*-

import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    expected_price_usd = fields.Float(
        string='Beklenen (USD)',
        digits='Product Price',
        compute='_compute_price_verification',
        store=False,
    )

    expected_price_try = fields.Float(
        string='Beklenen (TRY)',
        digits='Product Price',
        compute='_compute_price_verification',
        store=False,
    )

    price_difference = fields.Float(
        string='Fark (TRY)',
        digits='Product Price',
        compute='_compute_price_verification',
        store=False,
    )

    price_match = fields.Boolean(
        string='Fiyat Uyuşuyor',
        compute='_compute_price_verification',
        store=False,
    )

    verification_note = fields.Char(
        string='Kontrol Notu',
        compute='_compute_price_verification',
        store=False,
    )

    @api.depends('product_id', 'price_unit', 'move_id.move_type',
                 'move_id.partner_id', 'move_id.invoice_date')
    def _compute_price_verification(self):
        usd_currency = self.env.ref('base.USD', raise_if_not_found=False)
        company_currency = self.env.company.currency_id

        for line in self:
            # Defaults
            line.expected_price_usd = 0.0
            line.expected_price_try = 0.0
            line.price_difference = 0.0
            line.price_match = True
            line.verification_note = ''

            # Sadece tedarikçi faturası ürün satırları
            if (not line.product_id
                    or line.move_id.move_type != 'in_invoice'
                    or line.display_type != 'product'):
                continue

            # Tedarikçi USD fiyatını bul
            usd_price = self._get_supplier_usd_price(
                line.product_id, line.move_id.partner_id)

            if not usd_price:
                line.price_match = False
                line.verification_note = 'Tedarikçi USD fiyatı tanımlanmamış'
                continue

            # USD → TRY dönüşümü (fatura tarihindeki kur)
            invoice_date = line.move_id.invoice_date or fields.Date.today()
            if usd_currency and company_currency and usd_currency != company_currency:
                expected_try = usd_currency._convert(
                    usd_price, company_currency,
                    self.env.company, invoice_date)
            else:
                expected_try = usd_price

            line.expected_price_usd = usd_price
            line.expected_price_try = expected_try
            line.price_difference = line.price_unit - expected_try

            # Sıfır tolerans: TRY para birimi hassasiyetinde karşılaştır (2 ondalık)
            if company_currency:
                line.price_match = company_currency.is_zero(line.price_difference)
            else:
                line.price_match = round(line.price_difference, 2) == 0.0

            if not line.price_match:
                line.verification_note = (
                    f'Fark: {line.price_difference:+.2f} TRY '
                    f'(Beklenen: {expected_try:.2f}, Fatura: {line.price_unit:.2f})'
                )

    @api.model
    def _get_supplier_usd_price(self, product, partner):
        """Ürünün tedarikçi USD fiyatını bul.

        Öncelik sırası:
        1. product.supplierinfo → fatura partneriyle eşleşen kayıt
        2. product.supplierinfo → herhangi bir tedarikçi kaydı
        3. product.template.xml_supplier_price (XML Import'tan)
        """
        template = product.product_tmpl_id

        # 1. Fatura partnerine ait supplierinfo
        if partner:
            supplier_info = self.env['product.supplierinfo'].search([
                ('product_tmpl_id', '=', template.id),
                ('partner_id', '=', partner.id),
            ], limit=1, order='sequence, id')
            if supplier_info and supplier_info.price:
                return supplier_info.price

        # 2. Herhangi bir tedarikçi kaydı
        any_supplier = self.env['product.supplierinfo'].search([
            ('product_tmpl_id', '=', template.id),
        ], limit=1, order='sequence, id')
        if any_supplier and any_supplier.price:
            return any_supplier.price

        # 3. xml_supplier_price (fallback)
        if hasattr(template, 'xml_supplier_price') and template.xml_supplier_price:
            return template.xml_supplier_price

        return 0.0
