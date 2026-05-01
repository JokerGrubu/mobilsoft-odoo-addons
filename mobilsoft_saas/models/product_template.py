# -*- coding: utf-8 -*-
"""
MobilSoft SaaS - Ürün Otomatik Yayınlama

MobilSoft kiracı şirketleri ürün eklediğinde:
- Ürün CepteTedarik web sitesinde otomatik yayınlanır (website_published=True)
- İsteyen firma "Sadece Benim" seçeneğiyle yayını kapatabilir

Mantık:
- product.template oluşturulurken şirket MobilSoft kiracısı ise
  CepteTedarik website_id otomatik set edilir ve is_published=True yapılır
- Firma sonradan mobilsoft_marketplace_publish alanını False yaparak gizleyebilir
"""

import logging
from odoo import api, models, fields

_logger = logging.getLogger(__name__)

# CepteTedarik website domain — dinamik arama için
CEPTETEDARIK_DOMAIN = 'ceptetedarik.com'


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    mobilsoft_marketplace_publish = fields.Boolean(
        string='CepteTedarik\'te Sat',
        default=True,
        help='Bu ürünü CepteTedarik pazaryerinde yayınla. '
             'Kapatırsanız ürün sadece şirketinizde görünür.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Ürün oluşturulduğunda CepteTedarik'te otomatik yayınla ve e-ticaret kategorisi map et."""
        records = super().create(vals_list)
        records.with_context(skip_public_categ_sync=True)._sync_public_category_from_internal()
        self._auto_publish_on_ceptetedarik(records)
        return records

    def write(self, vals):
        """mobilsoft_marketplace_publish değiştiğinde website publish durumunu güncelle."""
        if self.env.context.get('skip_public_categ_sync'):
            return super().write(vals)

        result = super().write(vals)

        if 'mobilsoft_marketplace_publish' in vals:
            self._sync_marketplace_publish()

        # XML import vs. dış etkenler e-ticaret kategorilerini bozmamalı.
        # categ_id veya public_categ_ids değişiyorsa, her halükarda sadece iç kategori ağacını baz al.
        if 'categ_id' in vals or 'public_categ_ids' in vals:
            self.with_context(skip_public_categ_sync=True)._sync_public_category_from_internal()

        return result

    def _sync_public_category_from_internal(self):
        """
        Ürünün iç kategorisi (categ_id) değiştiğinde,
        e-ticaret kategorisini (public_categ_ids) senkronize eder.
        Sadece tam eşleşen ağacı tutar, diğer (bozuk/fazla) e-ticaret kategorilerini temizler.
        """
        PublicCategory = self.env['product.public.category'].sudo()
        for product in self:
            if not product.categ_id or product.categ_id.name == 'All':
                product.sudo().write({'public_categ_ids': [(5, 0, 0)]})
                continue

            # İç kategori ile aynı isimde e-ticaret kategorisi ara
            pc = PublicCategory.search([('name', '=', product.categ_id.name)], limit=1)

            # Bulunamazsa ve bu bir XML kaynağı ya da genel ürün değişimi ise oluştur
            if not pc:
                parent_pc_id = False
                if product.categ_id.parent_id and product.categ_id.parent_id.name != 'All':
                    parent_old = PublicCategory.search([('name', '=', product.categ_id.parent_id.name)], limit=1)
                    if parent_old:
                        parent_pc_id = parent_old.id

                pc = PublicCategory.create({
                    'name': product.categ_id.name,
                    'parent_id': parent_pc_id
                })

            # Ürünün e-ticaret kategorilerini SADECE bu kategori yapacak şekilde eziyoruz (6,0)
            product.sudo().write({'public_categ_ids': [(6, 0, [pc.id])]})

    def _auto_publish_on_ceptetedarik(self, records):
        """
        MobilSoft kiracı şirketlerin ürünlerini CepteTedarik'te otomatik yayınla.
        """
        try:
            ceptetedarik = self.env['website'].sudo().search([
                ('domain', 'like', CEPTETEDARIK_DOMAIN)
            ], limit=1)

            if not ceptetedarik:
                return  # CepteTedarik website kurulmamış, atla

            for product in records:
                company = product.company_id
                if not company:
                    continue

                # Sadece MobilSoft kiracı şirketlerin ürünleri otomatik yayınlanır
                if not company.mobilsoft_tenant:
                    continue

                if not product.mobilsoft_marketplace_publish:
                    continue

                try:
                    product.sudo().write({
                        'website_id': ceptetedarik.id,
                        'is_published': True,
                    })
                    _logger.info(
                        'MobilSoft Marketplace: "%s" ürünü CepteTedarik\'te yayınlandı '
                        '(şirket: %s)',
                        product.name, company.name
                    )
                except Exception as e:
                    _logger.warning(
                        'MobilSoft Marketplace: "%s" ürünü yayınlanamadı: %s',
                        product.name, e
                    )

        except Exception as e:
            _logger.warning('MobilSoft Marketplace: auto-publish hatası: %s', e)

    def _sync_marketplace_publish(self):
        """
        mobilsoft_marketplace_publish alanı değiştiğinde
        CepteTedarik'teki yayın durumunu güncelle.
        """
        try:
            ceptetedarik = self.env['website'].sudo().search([
                ('domain', 'like', CEPTETEDARIK_DOMAIN)
            ], limit=1)

            if not ceptetedarik:
                return

            for product in self:
                if not product.company_id or not product.company_id.mobilsoft_tenant:
                    continue

                if product.mobilsoft_marketplace_publish:
                    # Yayınla
                    product.sudo().write({
                        'website_id': ceptetedarik.id,
                        'is_published': True,
                    })
                    _logger.info(
                        'MobilSoft Marketplace: "%s" CepteTedarik\'te yayına alındı',
                        product.name
                    )
                else:
                    # Yayından kaldır
                    product.sudo().write({'is_published': False})
                    _logger.info(
                        'MobilSoft Marketplace: "%s" CepteTedarik\'ten kaldırıldı',
                        product.name
                    )
        except Exception as e:
            _logger.warning('MobilSoft Marketplace: sync hatası: %s', e)

    def action_toggle_marketplace(self):
        """
        Ürün listesi/form butonundan CepteTedarik yayın durumunu aç/kapat.
        """
        for product in self:
            new_val = not product.mobilsoft_marketplace_publish
            product.write({'mobilsoft_marketplace_publish': new_val})
        return True
