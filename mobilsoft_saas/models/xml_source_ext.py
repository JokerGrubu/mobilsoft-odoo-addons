# -*- coding: utf-8 -*-
"""
MobilSoft SaaS - XML Kaynak CepteTedarik Entegrasyonu (FAZE 4)

xml.product.source modeline CepteTedarik yayın alanı ekler.
Dış firmalar XML feed tanımladığında ürünler otomatik CepteTedarik'te yayınlanır.

Çalışma mantığı:
  - xml.product.source kaydında `ceptetedarik_publish = True` ise
  - Bu kaynaktan import edilen tüm ürünler website_id=CepteTedarik, is_published=True olur
  - is_dropship=True ve xml_source_id bu kaynağa set edilir
  - `action_publish_on_ceptetedarik()` ile manuel de tetiklenebilir
"""

import logging
import re
from odoo import api, models, fields

_logger = logging.getLogger(__name__)

CEPTETEDARIK_DOMAIN = 'ceptetedarik.com'


class XmlProductSourceCepteTedarik(models.Model):
    _inherit = 'xml.product.source'

    # ——— CepteTedarik Entegrasyonu ———
    ceptetedarik_publish = fields.Boolean(
        string='CepteTedarik\'te Yayınla',
        default=True,
        help='Bu XML kaynağından içe aktarılan ürünler '
             'CepteTedarik pazaryerinde otomatik yayınlansın.',
    )
    ceptetedarik_is_dropship = fields.Boolean(
        string='Dropship Olarak İşaretle',
        default=True,
        help='Ürünler dropship olarak işaretlensin '
             '(stok tutulmaz, sipariş tedarikçiye iletilir).',
    )
    ceptetedarik_company_id = fields.Many2one(
        'res.company',
        string='Dış Firma Şirketi',
        help='Bu XML kaynağına ait dış firmanın Odoo şirketi. '
             'Boşsa MobilSoft Platform şirketi kullanılır.',
    )
    sku_prefix = fields.Char(
        string='SKU Önek',
        help='Kaynaktan gelen SKU için eklenecek zorunlu önek (ör: EM-, TH-, AP-).',
    )

    # ---------- Internal helpers ----------
    def _resolve_import_company(self):
        """This source's target company for import and multi-company safety."""
        self.ensure_one()
        return self.ceptetedarik_company_id or self.env.company

    def _with_company_context(self):
        """Return source record with import company and minimal company context."""
        self.ensure_one()
        company = self._resolve_import_company()
        company_id = company.id or self.env.company.id
        ctx = dict(self.env.context or {})
        ctx.update({
            'force_company': company_id,
            'allowed_company_ids': [company_id],
        })
        return self.with_company(company_id).with_context(ctx)

    def _normalize_sku_prefix(self, sku, prefix):
        """Ensure SKU has prefix, without double prefixing."""
        if not sku or not prefix:
            return sku

        sku = str(sku).strip()
        prefix = str(prefix).strip().upper()
        if not prefix:
            return sku

        norm = re.sub(r'\s+', '', prefix).replace('_', '-')
        if not norm.endswith('-'):
            norm = f'{norm}-'

        if sku.upper().startswith((prefix.upper(), norm.upper())):
            return sku
        return f"{norm}{sku}"

    def _prepare_company_product_vals(self, vals):
        """Force imported products into the supplier company."""
        self.ensure_one()
        company = self._resolve_import_company()
        prepared = dict(vals or {})
        prepared['company_id'] = company.id
        return prepared

    def _accept_product_for_source(self, product):
        """
        Allow matching only inside the same company or the same XML source.
        Legacy global records are accepted only if they already belong to this source.
        """
        self.ensure_one()
        if not product or not product.exists():
            return False

        company = self._resolve_import_company()
        if product.company_id and product.company_id.id == company.id:
            return True
        if not product.company_id and product.xml_source_id and product.xml_source_id.id == self.id:
            return True
        return False

    def _normalize_existing_source_products(self):
        """
        Repair earlier imports that were created without company_id / SKU prefix.
        """
        self.ensure_one()
        company = self._resolve_import_company()
        products = self.env['product.template'].sudo().search([
            ('xml_source_id', '=', self.id),
        ])
        for product in products:
            vals = {}
            if product.company_id != company:
                vals['company_id'] = company.id
            normalized_sku = self._normalize_sku_prefix(product.default_code, self.sku_prefix)
            if normalized_sku and normalized_sku != product.default_code:
                vals['default_code'] = normalized_sku
            if vals:
                product.write(vals)
        return len(products)

    # ---------- Overrides ----------
    def _extract_product_data(self, element):
        """Inject SKUs with source-specific prefix before import matching/building."""
        data = super()._extract_product_data(element)
        if not data:
            return data
        data['sku'] = self._normalize_sku_prefix(data.get('sku'), self.sku_prefix)
        return data

    def _find_existing_product(self, data):
        """
        Prevent cross-company duplicates by forcing source company scope.
        """
        self.ensure_one()
        scoped = self._with_company_context()
        product, match_type = super(XmlProductSourceCepteTedarik, scoped)._find_existing_product(data)
        if self._accept_product_for_source(product):
            return product, match_type

        sku = (data.get('sku') or '').strip()
        barcode = (data.get('barcode') or '').strip()
        name = (data.get('name') or '').strip()
        company = self._resolve_import_company()
        ProductT = self.env['product.template'].sudo().with_context(active_test=False)
        domains = []
        if sku:
            domains.append([('default_code', '=', sku), ('company_id', '=', company.id)])
            domains.append([('default_code', '=', sku), ('xml_source_id', '=', self.id)])
        if barcode:
            domains.append([('barcode', '=', barcode), ('company_id', '=', company.id)])
            domains.append([('barcode', '=', barcode), ('xml_source_id', '=', self.id)])
        if name:
            domains.append([('name', '=ilike', name), ('company_id', '=', company.id)])
            domains.append([('name', '=ilike', name), ('xml_source_id', '=', self.id)])

        for domain in domains:
            product = ProductT.search(domain, limit=1)
            if product:
                return product, 'source_company_exact'
        return None, None

    def _find_or_create_base_product(self, base_name, data, cost_price):
        product = super()._find_or_create_base_product(base_name, data, cost_price)
        if product:
            vals = self._prepare_company_product_vals({})
            normalized_sku = self._normalize_sku_prefix(product.default_code, self.sku_prefix)
            if normalized_sku and normalized_sku != product.default_code:
                vals['default_code'] = normalized_sku
            product.sudo().write(vals)
        return product

    def _create_product(self, data, cost_price, xml_price):
        product = super()._create_product(data, cost_price, xml_price)
        if product:
            vals = self._prepare_company_product_vals({})
            normalized_sku = self._normalize_sku_prefix(product.default_code, self.sku_prefix)
            if normalized_sku and normalized_sku != product.default_code:
                vals['default_code'] = normalized_sku
            product.sudo().write(vals)
        return product

    def _update_product(self, product, data, cost_price, xml_price):
        result = super()._update_product(product, data, cost_price, xml_price)
        if product:
            vals = self._prepare_company_product_vals({})
            normalized_sku = self._normalize_sku_prefix(product.default_code, self.sku_prefix)
            if normalized_sku and normalized_sku != product.default_code:
                vals['default_code'] = normalized_sku
            product.sudo().write(vals)
        return result

    def action_publish_on_ceptetedarik(self):
        """
        Bu kaynaktan gelen tüm ürünleri CepteTedarik'te yayınla.
        Manuel buton — import sonrası veya istenildiğinde tetiklenebilir.
        """
        self.ensure_one()
        count = self._publish_source_products_on_ceptetedarik()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'CepteTedarik Yayın',
                'message': f'{count} ürün CepteTedarik\'te yayına alındı.',
                'type': 'success',
                'sticky': False,
            }
        }

    def _publish_source_products_on_ceptetedarik(self):
        """
        Bu kaynaktaki ürünleri CepteTedarik'te yayınla.
        Dönüş: yayınlanan ürün sayısı
        """
        if not self.ceptetedarik_publish:
            return 0

        ceptetedarik = self.env['website'].sudo().search([
            ('domain', 'like', CEPTETEDARIK_DOMAIN)
        ], limit=1)

        if not ceptetedarik:
            _logger.warning('CepteTedarik website bulunamadı, yayın atlandı')
            return 0

        # Bu kaynaktan gelen ürünleri bul
        products = self.env['product.template'].sudo().search([
            ('xml_source_id', '=', self.id),
        ])

        if not products:
            _logger.info('XML kaynağı %s: Yayınlanacak ürün yok', self.name)
            return 0

        publish_vals = {
            'website_id': ceptetedarik.id,
            'is_published': True,
        }
        if self.ceptetedarik_is_dropship:
            publish_vals['is_dropship'] = True

        products.sudo().write(publish_vals)

        _logger.info(
            'CepteTedarik: %d ürün yayınlandı (kaynak: %s)',
            len(products), self.name
        )
        return len(products)

    def action_import_products(self):
        """
        Orjinal import metodunu çağır, sonra CepteTedarik'te yayınla.
        """
        result = None
        for source in self:
            source._normalize_existing_source_products()
            scoped = source._with_company_context()
            result = super(XmlProductSourceCepteTedarik, scoped).action_import_products()

            # Import sonrası otomatik yayın
            if source.ceptetedarik_publish:
                try:
                    count = source._publish_source_products_on_ceptetedarik()
                    _logger.info(
                        'XML Import sonrası CepteTedarik yayın: %d ürün (kaynak: %s)',
                        count, source.name
                    )
                except Exception as e:
                    _logger.warning(
                        'CepteTedarik import-sonrası yayın hatası (kaynak: %s): %s',
                        source.name, e
                    )
                    # Kritik değil, import başarısı etkilenmesin

        return result or {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'CepteTedarik Yayın',
                'message': 'Kaynak listesi işlenerek cepteTedarik yayını tetiklendi.',
                'type': 'info',
                'sticky': False,
            }
        }
