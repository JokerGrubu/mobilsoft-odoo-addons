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
        """Ürün eşleştirmesi yap veya yeni ürün oluştur"""
        self.ensure_one()

        # Eşleştirme yap
        product, match_status, match_score = self._find_matching_product()

        # Bulunamazsa yeni ürün oluştur
        if not product:
            product = self._create_product_from_line()
            match_status = 'created'
            match_score = 100.0

        # Güncelle
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
        Ürün eşleştirme yap (4 aşamalı):
        1. Barkod
        2. Ürün Kodu
        3. Tam İsim
        4. Benzer İsim (fuzzy matching)
        """
        Product = self.env['product.product']

        # 1. Barkod ile ara
        if self.barcode:
            product = Product.search([('barcode', '=', self.barcode)], limit=1)
            if product:
                return product, 'matched_barcode', 100.0

        # 2. Ürün Kodu ile ara
        if self.product_code:
            product = Product.search([('default_code', '=', self.product_code)], limit=1)
            if product:
                return product, 'matched_code', 100.0

        # 3. Tam İsim ile ara
        if self.product_name:
            product = Product.search([('name', '=', self.product_name)], limit=1)
            if product:
                return product, 'matched_name', 100.0

            # 4. Benzer İsim (ILIKE) - kısmi eşleşme
            product = Product.search([('name', 'ilike', self.product_name)], limit=1)
            if product:
                score = self._calculate_similarity(self.product_name, product.name)
                return product, 'matched_fuzzy', score

            # 5. Kelimelere böl ve ara (fuzzy matching)
            words = self.product_name.split()
            if len(words) > 1:
                # En az 2 kelime içeren ürünleri ara
                domain = []
                for word in words:
                    if len(word) > 2:  # 2 harften uzun kelimeler
                        domain.append(('name', 'ilike', word))

                if domain:
                    products = Product.search(domain, limit=10)
                    if products:
                        # En yüksek benzerlik skoruna sahip ürünü bul
                        best_product = None
                        best_score = 0.0

                        for product in products:
                            score = self._calculate_similarity(self.product_name, product.name)
                            if score > best_score and score > 60.0:  # En az %60 benzerlik
                                best_score = score
                                best_product = product

                        if best_product:
                            return best_product, 'matched_fuzzy', best_score

        return None, 'not_matched', 0.0

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
