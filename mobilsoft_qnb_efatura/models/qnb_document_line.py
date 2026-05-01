# -*- coding: utf-8 -*-
"""
QNB Belge Satırları (Fatura İçeriği)
XML'den parse edilen ürün/hizmet satırları
"""

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class QnbDocumentLine(models.Model):
    _name = 'qnb.document.line'
    _description = 'QNB Belge Satırı'
    _order = 'sequence, id'

    document_id = fields.Many2one(
        'qnb.document',
        string='QNB Belgesi',
        required=True,
        ondelete='cascade'
    )

    sequence = fields.Integer(
        string='Sıra',
        default=10
    )

    # Ürün Bilgileri
    product_id = fields.Many2one(
        'product.product',
        string='Eşleşen Ürün',
        help='Odoo\'daki eşleşen ürün'
    )

    product_name = fields.Char(
        string='Ürün Adı',
        required=True,
        help='XML\'den gelen ürün adı'
    )

    product_description = fields.Text(
        string='Açıklama',
        help='XML\'den gelen ürün açıklaması'
    )

    product_code = fields.Char(
        string='Ürün Kodu',
        help='Satıcının ürün kodu (SellersItemIdentification)'
    )

    barcode = fields.Char(
        string='Barkod',
        help='GTIN/EAN barkod'
    )

    # Miktar ve Birim
    quantity = fields.Float(
        string='Miktar',
        default=1.0,
        digits='Product Unit of Measure'
    )

    uom_code = fields.Char(
        string='Birim Kodu',
        help='UBL birim kodu (LTR, KGM, C62, vb.)'
    )

    # Fiyat
    price_unit = fields.Float(
        string='Birim Fiyat',
        digits='Product Price'
    )

    price_subtotal = fields.Float(
        string='Ara Toplam',
        help='Vergisiz tutar',
        digits='Account'
    )

    # Vergi
    tax_percent = fields.Float(
        string='KDV %',
        help='KDV oranı'
    )

    tax_amount = fields.Float(
        string='KDV Tutarı',
        digits='Account'
    )

    # Eşleştirme Durumu
    match_status = fields.Selection([
        ('matched_barcode', 'Barkod ile Eşleşti'),
        ('matched_code', 'Ürün Kodu ile Eşleşti'),
        ('matched_name', 'İsim ile Eşleşti'),
        ('matched_fuzzy', 'Benzer İsim ile Eşleşti'),
        ('not_matched', 'Eşleşmedi'),
        ('created', 'Yeni Ürün Oluşturuldu')
    ], string='Eşleştirme Durumu', default='not_matched')

    match_score = fields.Float(
        string='Benzerlik Skoru',
        help='Fuzzy matching skoru (0-100)',
        digits=(5, 2)
    )

    notes = fields.Text(
        string='Notlar'
    )

    @api.depends('product_id')
    def _compute_display_name(self):
        for line in self:
            if line.product_id:
                line.display_name = f"{line.product_name} → {line.product_id.name}"
            else:
                line.display_name = line.product_name or 'Satır'

    def action_match_product(self):
        """Ürün eşleştirmesi yap (Nilvera/UBL ile aynı mantık - yeni ürün oluşturmaz)"""
        self.ensure_one()

        product, match_status, match_score = self._find_matching_product()

        if not product:
            self.write({'match_status': 'not_matched', 'match_score': 0.0})
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Eşleşme Bulunamadı'),
                    'message': _('"%s" için Odoo\'da ürün bulunamadı. Barkod veya ürün kodu ile stok kartı oluşturun.', self.product_name or ''),
                    'type': 'warning',
                    'sticky': False,
                }
            }

        self.write({
            'product_id': product.id,
            'match_status': match_status,
            'match_score': match_score
        })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '✅ Eşleştirme Tamamlandı',
                'message': f'{self.product_name} → {product.name} ({match_status})',
                'type': 'success',
            }
        }

    def _find_matching_product(self):
        """
        Nilvera/UBL ile aynı: Odoo standart _retrieve_product kullanır.
        Eşleştirme sırası: barkod → default_code → name (tam) → name (ilike)
        Yeni ürün oluşturmaz (Nilvera gibi).
        """
        Product = self.env['product.product']
        company = self.document_id.company_id or self.env.company

        product_vals = {
            'default_code': self.product_code or '',
            'barcode': self.barcode or '',
            'name': (self.product_name or self.product_description or '').split('\n', 1)[0] or '',
        }
        product_vals = {k: v for k, v in product_vals.items() if v}

        if not product_vals:
            return None, 'not_matched', 0.0

        product = Product._retrieve_product(company=company, **product_vals)

        if product:
            if product_vals.get('barcode') and product.barcode == product_vals['barcode']:
                status = 'matched_barcode'
            elif product_vals.get('default_code') and product.default_code == product_vals['default_code']:
                status = 'matched_code'
            else:
                status = 'matched_name'
            return product, status, 100.0

        return None, 'not_matched', 0.0

    @staticmethod
    def _extract_product_codes_from_name_static(product_name):
        """
        Ürün isminden olası kodları çıkar (Static method)
        Örnek: "POWERWAY CC34 ARAÇ ŞARJ" → ["CC34", "POWERWAY"]
        Örnek: "POWERWAY QCT30 ŞARJ CİHAZI" → ["QCT30", "POWERWAY"]
        """
        if not product_name:
            return []

        import re
        codes = []

        # Büyük harfle başlayan kısa kelimeler (2-10 karakter arası, rakam içerebilir)
        # CC34, QCT30, X633, IP27 gibi
        pattern = r'\b([A-Z]{2,3}\d{2,4}|[A-Z]{2,4}\d{1,3})\b'
        matches = re.findall(pattern, product_name.upper())
        codes.extend(matches)

        # Marka ismi (ilk kelime genelde)
        words = product_name.upper().split()
        if words and len(words[0]) > 3:  # En az 4 harfli ilk kelime
            first_word = words[0].strip()
            if first_word not in codes and first_word.isalpha():
                codes.append(first_word)

        return list(set(codes))  # Tekrarları temizle

    def _extract_product_codes_from_name(self):
        """
        Ürün isminden olası kodları çıkar
        Örnek: "POWERWAY CC34 ARAÇ ŞARJ" → ["CC34", "POWERWAY"]
        Örnek: "POWERWAY QCT30 ŞARJ CİHAZI" → ["QCT30", "POWERWAY"]
        """
        return self._extract_product_codes_from_name_static(self.product_name)

    def _save_manufacturer_code_to_product(self, product):
        """
        QNB'deki product_code'u (üretici stok kodu) Odoo ürününe kaydet
        Eğer Odoo'daki default_code boşsa veya farklıysa, not olarak ekle
        """
        if not self.product_code or not product:
            return

        # Eğer ürünün kodu yoksa, QNB kodunu kaydet
        if not product.default_code:
            try:
                product.write({'default_code': self.product_code})
                _logger.info(f"✅ Ürün kodu kaydedildi: {product.name} → {self.product_code}")
            except Exception as e:
                _logger.warning(f"⚠️ Ürün kodu kaydedilemedi: {e}")
        elif product.default_code != self.product_code:
            # Farklı kod varsa, nota ekle (gelecekte supplier_info olarak eklenebilir)
            _logger.debug(f"ℹ️ Alternatif kod: {product.name} (Odoo: {product.default_code}, QNB: {self.product_code})")

    def _calculate_similarity(self, str1, str2):
        """İki string arasındaki benzerlik skorunu hesapla (0-100)"""
        if not str1 or not str2:
            return 0.0

        # Küçük harfe çevir ve boşlukları temizle
        s1 = str1.lower().strip()
        s2 = str2.lower().strip()

        # Tam eşleşme
        if s1 == s2:
            return 100.0

        # Birisi diğerini içeriyor mu?
        if s1 in s2 or s2 in s1:
            shorter = min(len(s1), len(s2))
            longer = max(len(s1), len(s2))
            return (shorter / longer) * 95.0

        # Levenshtein distance (basit versiyon)
        # Ortak kelime sayısı
        words1 = set(s1.split())
        words2 = set(s2.split())

        if not words1 or not words2:
            return 0.0

        common_words = words1.intersection(words2)
        total_words = words1.union(words2)

        if not total_words:
            return 0.0

        # Jaccard benzerliği
        score = (len(common_words) / len(total_words)) * 100.0

        return round(score, 2)

    def _create_product_from_line(self):
        """Satırdan yeni ürün oluştur"""
        Product = self.env['product.product']

        vals = {
            'name': self.product_name or self.product_description or 'Bilinmeyen Ürün',
            'type': 'consu',  # Tüketilebilir (stok takipsiz)
            'purchase_ok': True if self.document_id.direction == 'incoming' else False,
            'sale_ok': True if self.document_id.direction == 'outgoing' else False,
        }

        if self.barcode:
            vals['barcode'] = self.barcode
        if self.product_code:
            vals['default_code'] = self.product_code
        if self.product_description:
            vals['description_purchase'] = self.product_description

        product = Product.create(vals)
        _logger.info(f"✅ Yeni ürün oluşturuldu: {product.name} (ID: {product.id})")

        return product

    @api.model
    def action_bulk_rematch_products(self):
        """
        Tüm eşleşmemiş ürünleri yeniden eşleştir
        Geliştirilmiş algoritma ile tekrar dene
        """
        lines = self.search([
            ('product_id', '=', False),
            ('match_status', 'in', ['not_matched', False])
        ])

        total = len(lines)
        matched = 0
        failed = 0

        _logger.info(f"🔄 {total} eşleşmemiş ürün satırı yeniden eşleştiriliyor...")

        for line in lines:
            try:
                product, match_status, match_score = line._find_matching_product()

                if product:
                    line.write({
                        'product_id': product.id,
                        'match_status': match_status,
                        'match_score': match_score
                    })
                    matched += 1
                    _logger.debug(f"✅ Eşleşti: {line.product_name} → {product.name} ({match_status})")
                else:
                    failed += 1
                    _logger.debug(f"❌ Eşleşmedi: {line.product_name}")

            except Exception as e:
                failed += 1
                _logger.error(f"❌ Hata: {line.product_name} → {e}")
                continue

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': '🔄 Toplu Ürün Eşleştirme',
                'message': f'Toplam: {total}\nEşleşti: {matched}\nEşleşmedi: {failed}',
                'type': 'success' if matched > 0 else 'warning',
                'sticky': True,
            }
        }
