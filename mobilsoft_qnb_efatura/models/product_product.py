# -*- coding: utf-8 -*-
"""
Ürün Modeli Genişletmesi
Harici sistem kodlarını takip etmek için
"""

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    # Harici Sistemlerden Gelen Kodlar
    qnb_product_code = fields.Char(
        string='QNB Ürün Kodu',
        help='QNB e-Fatura/e-Arşiv XML\'inden gelen ürün kodu (SellersItemIdentification)',
        index=True
    )

    bizimhesap_product_code = fields.Char(
        string='BizimHesap Ürün Kodu',
        help='BizimHesap sisteminden gelen ürün kodu',
        index=True
    )

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

    # SQL Constraint: QNB ve BizimHesap kodları unique olmalı (boş değilse)
    _sql_constraints = [
        ('qnb_product_code_unique',
         'UNIQUE(qnb_product_code)',
         'Bu QNB ürün kodu zaten başka bir üründe kullanılıyor!'),
        ('bizimhesap_product_code_unique',
         'UNIQUE(bizimhesap_product_code)',
         'Bu BizimHesap ürün kodu zaten başka bir üründe kullanılıyor!')
    ]

    def match_or_create_from_external(self, source, external_data):
        """
        Harici sistemden gelen veriye göre ürün eşleştir veya oluştur

        Args:
            source: 'qnb', 'bizimhesap', 'xml'
            external_data: dict with keys:
                - product_code: Harici sistem ürün kodu
                - product_name: Ürün adı
                - barcode: Barkod (opsiyonel)
                - description: Açıklama (opsiyonel)

        Returns:
            (product, matched, match_type) tuple
            - product: product.product kaydı
            - matched: True/False (eşleşti mi yoksa yeni mi oluşturuldu)
            - match_type: 'external_code', 'barcode', 'default_code', 'name', 'fuzzy', 'created'
        """
        self.ensure_one() if len(self) > 0 else None
        Product = self.env['product.product']

        product_code = external_data.get('product_code')
        product_name = external_data.get('product_name', '')
        barcode = external_data.get('barcode')
        description = external_data.get('description', '')

        # 1. ÖNCE HARICI KOD KONTROLÜ (en hızlı ve güvenilir)
        if product_code:
            # Source'a göre ilgili alanda ara
            if source == 'qnb':
                product = Product.search([('qnb_product_code', '=', product_code)], limit=1)
                if product:
                    _logger.debug(f"✅ QNB kodu ile eşleşti: {product_code} → {product.name}")
                    return product, True, 'external_code'
            elif source == 'bizimhesap':
                product = Product.search([('bizimhesap_product_code', '=', product_code)], limit=1)
                if product:
                    _logger.debug(f"✅ BizimHesap kodu ile eşleşti: {product_code} → {product.name}")
                    return product, True, 'external_code'

        # 2. BARKOD İLE KONTROL
        if barcode:
            product = Product.search([('barcode', '=', barcode)], limit=1)
            if product:
                # Harici kodu kaydet
                self._save_external_code(product, source, product_code)
                _logger.info(f"✅ Barkod ile eşleşti: {barcode} → {product.name}")
                return product, True, 'barcode'

        # 3. ODOO ÜRÜN KODU (default_code) İLE KONTROL
        if product_code:
            product = Product.search([('default_code', '=', product_code)], limit=1)
            if product:
                self._save_external_code(product, source, product_code)
                _logger.info(f"✅ Default code ile eşleşti: {product_code} → {product.name}")
                return product, True, 'default_code'

        # 4. ÜRÜN İSMİNDEN KOD ÇIKARMA (Powerway CC34 → CC34)
        from . import qnb_document_line
        extracted_codes = qnb_document_line.QnbDocumentLine._extract_product_codes_from_name_static(product_name)
        if extracted_codes:
            for code in extracted_codes:
                product = Product.search([('default_code', '=', code)], limit=1)
                if product:
                    self._save_external_code(product, source, product_code)
                    _logger.info(f"✅ İsimden çıkarılan kod ile eşleşti: {code} → {product.name}")
                    return product, True, 'default_code'

                product = Product.search([('default_code', 'ilike', code)], limit=1)
                if product:
                    self._save_external_code(product, source, product_code)
                    _logger.info(f"✅ İsimden çıkarılan kod (fuzzy) ile eşleşti: {code} → {product.name}")
                    return product, True, 'default_code'

        # 5. AÇIKLAMADA KOD ARAMA
        if description:
            # Açıklamadaki kodları bul
            extracted_codes_desc = qnb_document_line.QnbDocumentLine._extract_product_codes_from_name_static(description)
            if extracted_codes_desc:
                for code in extracted_codes_desc:
                    product = Product.search([('default_code', '=', code)], limit=1)
                    if product:
                        self._save_external_code(product, source, product_code)
                        _logger.info(f"✅ Açıklamadan çıkarılan kod ile eşleşti: {code} → {product.name}")
                        return product, True, 'default_code'

        # 6. TAM İSİM İLE KONTROL
        if product_name:
            # name alanı jsonb olabilir, product_tmpl_id üzerinden kontrol edelim
            product = Product.search([('name', '=', product_name)], limit=1)
            if product:
                self._save_external_code(product, source, product_code)
                _logger.info(f"✅ Tam isim ile eşleşti: {product_name} → {product.name}")
                return product, True, 'name'

        # 7. BENZER İSİM (FUZZY MATCHING)
        if product_name:
            product = Product.search([('name', 'ilike', product_name)], limit=1)
            if product:
                self._save_external_code(product, source, product_code)
                _logger.info(f"✅ Benzer isim ile eşleşti: {product_name} → {product.name}")
                return product, True, 'fuzzy'

            # Kelimelere ayırarak ara
            words = product_name.split()
            if len(words) > 1:
                domain = []
                for word in words:
                    if len(word) > 2:
                        domain.append(('name', 'ilike', word))

                if domain:
                    products = Product.search(domain, limit=5)
                    if products:
                        # En yüksek benzerlik skoruna sahip ürünü bul
                        best_product = None
                        best_score = 0.0

                        for product in products:
                            score = self._calculate_similarity(product_name, product.name)
                            if score > best_score and score > 60.0:
                                best_score = score
                                best_product = product

                        if best_product:
                            self._save_external_code(best_product, source, product_code)
                            _logger.info(f"✅ Fuzzy matching ile eşleşti (skor: {best_score}): {product_name} → {best_product.name}")
                            return best_product, True, 'fuzzy'

        # 8. HİÇBİR EŞLEŞME YOK - YENİ ÜRÜN OLUŞTURMA İSTENİYOR MU?
        _logger.warning(f"❌ Eşleşme bulunamadı: {product_name} (Kod: {product_code})")
        return None, False, 'not_matched'

    def _save_external_code(self, product, source, code):
        """Harici sistem kodunu ürüne kaydet"""
        if not code or not product:
            return

        vals = {
            'last_matched_source': source,
            'last_matched_date': fields.Datetime.now()
        }

        if source == 'qnb' and not product.qnb_product_code:
            vals['qnb_product_code'] = code
        elif source == 'bizimhesap' and not product.bizimhesap_product_code:
            vals['bizimhesap_product_code'] = code

        try:
            product.write(vals)
            _logger.debug(f"✅ Harici kod kaydedildi: {product.name} → {source}: {code}")
        except Exception as e:
            _logger.warning(f"⚠️ Harici kod kaydedilemedi: {e}")

    def _calculate_similarity(self, str1, str2):
        """İki string arasındaki benzerlik skorunu hesapla (0-100)"""
        if not str1 or not str2:
            return 0.0

        s1 = str(str1).lower().strip()
        s2 = str(str2).lower().strip()

        if s1 == s2:
            return 100.0

        if s1 in s2 or s2 in s1:
            shorter = min(len(s1), len(s2))
            longer = max(len(s1), len(s2))
            return (shorter / longer) * 95.0

        words1 = set(s1.split())
        words2 = set(s2.split())

        if not words1 or not words2:
            return 0.0

        common_words = words1.intersection(words2)
        total_words = words1.union(words2)

        if not total_words:
            return 0.0

        score = (len(common_words) / len(total_words)) * 100.0
        return round(score, 2)
