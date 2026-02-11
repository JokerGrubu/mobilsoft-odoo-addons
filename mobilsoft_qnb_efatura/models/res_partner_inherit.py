# -*- coding: utf-8 -*-
"""
Partner Modeli Genişletmesi
Harici sistem kodlarını takip etmek için
"""

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # VKN/TCKN standart vat alanında tutuluyor; eşleştirme vat ile yapılıyor (qnb_partner_vkn kaldırıldı).

    external_partner_codes = fields.Text(
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

    def _vat_normalize(self, vat_value):
        """VKN/TCKN'dan sadece rakamları al (TR, boşluk, tire temizlenir)."""
        if not vat_value:
            return ''
        return ''.join(c for c in str(vat_value).strip() if c.isdigit())

    def match_or_create_from_external(self, source, external_data):
        """
        Harici sistemden gelen veriye göre partner eşleştir veya oluştur

        Args:
            source: 'qnb', 'bizimhesap', 'xml'
            external_data: dict with keys:
                - vat: VKN/TCKN
                - name: Partner adı
                - email: E-posta (opsiyonel)
                - phone: Telefon (opsiyonel)
                - street: Adres (opsiyonel)
                - city: Şehir (opsiyonel)

        Returns:
            (partner, matched, match_type) tuple
            - partner: res.partner kaydı
            - matched: True/False (eşleşti mi yoksa yeni mi oluşturuldu)
            - match_type: 'external_code', 'vat', 'name', 'email', 'created'
        """
        self.ensure_one() if len(self) > 0 else None
        Partner = self.env['res.partner']

        vat = external_data.get('vat', '').strip()
        name = external_data.get('name', '').strip()
        email = external_data.get('email', '').strip()
        phone = external_data.get('phone', '').strip()

        # VKN/TCKN temizle (TR prefix, boşluklar)
        if vat:
            vat = vat.replace('TR', '').replace(' ', '').replace('-', '')

        # 1. ÖNCE HARICI KOD KONTROLÜ (VKN/TCKN) — standart vat ile
        if vat:
            digits = self._vat_normalize(vat)
            if digits:
                # vat alanında rakam veya TR+rakam olarak ara
                partner = Partner.search([
                    '|', ('vat', '=', digits), ('vat', '=', f'TR{digits}')
                ], limit=1)
                if partner:
                    _logger.debug(f"✅ VAT ile eşleşti ({source}): {vat} → {partner.name}")
                    return partner, True, 'external_code'
            if source == 'bizimhesap':
                ref_code = (external_data.get('ref') or external_data.get('code') or '').strip()
                if ref_code:
                    partner = Partner.search([('ref', '=', ref_code)], limit=1)
                    if partner:
                        _logger.debug(f"✅ BizimHesap ref ile eşleşti: {ref_code} → {partner.name}")
                        return partner, True, 'external_code'

        # 2. VAT (VKN/TCKN) İLE KONTROL
        if vat:
            # Standart vat alanında ara
            partner = Partner.search([('vat', '=', vat)], limit=1)
            if partner:
                # Harici kodu kaydet
                self._save_external_code(partner, source, vat)
                _logger.info(f"✅ VAT ile eşleşti: {vat} → {partner.name}")
                return partner, True, 'vat'

            # TR prefix ile ara
            partner = Partner.search([('vat', '=', f'TR{vat}')], limit=1)
            if partner:
                self._save_external_code(partner, source, vat)
                _logger.info(f"✅ VAT (TR prefix) ile eşleşti: {vat} → {partner.name}")
                return partner, True, 'vat'

        # 3. E-POSTA İLE KONTROL
        if email:
            partner = Partner.search([('email', '=', email)], limit=1)
            if partner:
                self._save_external_code(partner, source, vat)
                _logger.info(f"✅ Email ile eşleşti: {email} → {partner.name}")
                return partner, True, 'email'

        # 4. TAM İSİM İLE KONTROL
        if name:
            partner = Partner.search([('name', '=', name)], limit=1)
            if partner:
                self._save_external_code(partner, source, vat)
                _logger.info(f"✅ Tam isim ile eşleşti: {name} → {partner.name}")
                return partner, True, 'name'

        # 5. BENZER İSİM (ILIKE)
        if name:
            partner = Partner.search([('name', 'ilike', name)], limit=1)
            if partner:
                self._save_external_code(partner, source, vat)
                _logger.info(f"✅ Benzer isim ile eşleşti: {name} → {partner.name}")
                return partner, True, 'name'

        # 6. HİÇBİR EŞLEŞME YOK
        _logger.warning(f"❌ Partner eşleşmesi bulunamadı: {name} (VKN: {vat})")
        return None, False, 'not_matched'

    def _save_external_code(self, partner, source, code):
        """Harici sistem kodunu partnere kaydet"""
        if not code or not partner:
            return

        vals = {
            'last_matched_source': source,
            'last_matched_date': fields.Datetime.now()
        }

        if source == 'qnb' and code and not partner.vat:
            vals['vat'] = f'TR{code}' if not (str(code).upper().startswith('TR')) else code
        elif source == 'bizimhesap' and code and not partner.ref:
            vals['ref'] = code

        try:
            partner.write(vals)
            _logger.debug(f"✅ Partner harici kod kaydedildi: {partner.name} → {source}: {code}")
        except Exception as e:
            _logger.warning(f"⚠️ Partner harici kod kaydedilemedi: {e}")
