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

    def match_or_create_from_external(self, source, external_data):
        """
        Harici sistemden gelen veriye göre partner eşleştir (oluşturmaz).

        Odoo standart _retrieve_partner kullanılır: vat, phone, email, name sırasıyla denenir.

        Args:
            source: 'qnb', 'bizimhesap', 'xml'
            external_data: dict with keys:
                - vat: VKN/TCKN
                - name: Partner adı
                - email: E-posta (opsiyonel)
                - phone: Telefon (opsiyonel)
                - ref: Cari kodu (BizimHesap - domain ile aranır)

        Returns:
            (partner, matched, match_type) tuple
            - partner: res.partner kaydı veya None
            - matched: True/False
            - match_type: 'vat', 'email', 'phone', 'name', 'ref', 'not_matched'
        """
        self.ensure_one() if len(self) > 0 else None
        Partner = self.env['res.partner']

        vat = (external_data.get('vat') or '').strip()
        name = (external_data.get('name') or '').strip()
        email = (external_data.get('email') or '').strip()
        phone = (external_data.get('phone') or external_data.get('mobile') or '').strip()

        # VKN/TCKN: TR prefix olmadan gönderilirse ekle (Odoo _retrieve_partner_with_vat için)
        vat_for_search = vat
        if vat and not str(vat).upper().startswith('TR'):
            vat_for_search = f'TR{vat.replace(" ", "").replace("-", "")}'

        # 1. BizimHesap ref (cari kodu) - _retrieve_partner domain ile
        if source == 'bizimhesap':
            ref_code = (external_data.get('ref') or external_data.get('code') or '').strip()
            if ref_code:
                partner = Partner._retrieve_partner(domain=[('ref', '=', ref_code)])
                if partner:
                    self._save_external_code(partner, source, vat or ref_code)
                    _logger.debug(f"✅ BizimHesap ref ile eşleşti: {ref_code} → {partner.name}")
                    return partner, True, 'ref'

        # 2. Odoo standart _retrieve_partner (vat → phone/email → name)
        partner = Partner._retrieve_partner(
            name=name or None,
            phone=phone or None,
            email=email or None,
            vat=vat_for_search or None,
        )
        if partner:
            self._save_external_code(partner, source, vat)
            _logger.debug(f"✅ Odoo _retrieve_partner ile eşleşti ({source}): {partner.name}")
            return partner, True, 'vat' if vat else ('email' if email else ('phone' if phone else 'name'))

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
