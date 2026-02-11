# -*- coding: utf-8 -*-
"""
QNB e-Solutions Fatura Gönderim Modülü
Nilvera uyumlu validasyon ve gönderim akışı
"""

import re
import uuid

from odoo import _, api, models


class AccountMoveSend(models.AbstractModel):
    _inherit = 'account.move.send'

    @api.model
    def _is_tr_qnb_applicable(self, move):
        return all([
            move.company_id.qnb_enabled,
            move.country_code == 'TR',
            move.is_invoice(include_receipts=True),
            move.qnb_state in ('not_sent', 'error'),
        ])

    @api.model
    def _is_tr_nilvera_applicable(self, move):
        """QNB kullanılıyorsa aynı fatura Nilvera ile gönderilmesin (mükerrer belge önleme)."""
        if move.company_id.qnb_enabled:
            return False
        return super()._is_tr_nilvera_applicable(move)

    def _get_all_extra_edis(self) -> dict:
        res = super()._get_all_extra_edis()
        res.update({'tr_qnb': {'label': _("by QNB e-Solutions"), 'is_applicable': self._is_tr_qnb_applicable}})
        return res

    # -------------------------------------------------------------------------
    # ATTACHMENTS (Nilvera uyumlu)
    # -------------------------------------------------------------------------

    def _get_invoice_extra_attachments(self, move):
        """QNB PDF'i mail eklerine ekle (Nilvera uyumlu)"""
        # EXTENDS 'account'
        attachments = super()._get_invoice_extra_attachments(move)
        if (
            move.qnb_state in ('sent', 'delivered', 'accepted')
            and move.message_main_attachment_id
            and move.message_main_attachment_id.id != move.invoice_pdf_report_id.id
        ):
            attachments += move.message_main_attachment_id
        return attachments

    # -------------------------------------------------------------------------
    # ALERTS - Validasyon Uyarıları (Nilvera uyumlu)
    # -------------------------------------------------------------------------

    def _get_alerts(self, moves, moves_data):
        """QNB gönderim öncesi validasyon uyarıları (Nilvera uyumlu)"""

        def _is_valid_qnb_name(move):
            """Fatura numarası QNB formatına uygun mu? (ABC2025123456789)"""
            try:
                _, parts = move._get_sequence_format_param(move.name)
                return (
                    parts['year'] != 0
                    and parts['year_length'] == 4
                    and parts['seq'] != 0
                    and re.match(r'^[A-Za-z0-9]{3}[^A-Za-z0-9]?$', parts['prefix1'])
                )
            except Exception:
                return True  # Hata durumunda geç

        alerts = super()._get_alerts(moves, moves_data)

        # QNB EDI seçili faturalar
        tr_qnb_moves = moves.filtered(lambda m: 'tr_qnb' in moves_data[m]['extra_edis'])

        if not tr_qnb_moves:
            return alerts

        # 1. Test modu uyarısı
        if self.env.company.country_code == 'TR' and self.env.company.qnb_environment == 'test':
            alerts['qnb_test_mode'] = {
                'level': 'info',
                'message': _("QNB Test modu aktif. Faturalar test ortamına gönderilecek."),
            }

        # 2. Şirket eksik alan kontrolü (VKN, adres, şehir, il)
        companies_missing_fields = tr_qnb_moves.filtered(
            lambda m: (
                not m.company_id.vat
                or not m.company_id.street
                or not m.company_id.city
                or not m.company_id.state_id
                or m.company_id.country_code != 'TR'
            )
        ).company_id

        if companies_missing_fields:
            alerts['qnb_companies_missing_fields'] = {
                'level': 'danger',
                'message': _(
                    "Şirket bilgileri eksik! Aşağıdaki şirketlerde VKN, Adres, Şehir veya İl eksik: %s"
                ) % ', '.join(companies_missing_fields.mapped('name')),
                'action_text': _("Şirketleri Görüntüle"),
                'action': companies_missing_fields._get_records_action(
                    name=_("Eksik Bilgili Şirketler")
                ),
            }

        # 3. Partner eksik alan kontrolü (VKN, adres, şehir, il, ülke)
        partners_missing_fields = tr_qnb_moves.filtered(
            lambda m: (
                not m.partner_id.vat
                or not m.partner_id.street
                or not m.partner_id.city
                or not m.partner_id.state_id
                or not m.partner_id.country_id
            )
        ).partner_id

        if partners_missing_fields:
            alerts['qnb_partners_missing_fields'] = {
                'level': 'danger',
                'message': _(
                    "Partner bilgileri eksik! VKN, Adres, Şehir, İl veya Ülke alanlarından en az biri eksik."
                ),
                'action_text': _("Partnerleri Görüntüle"),
                'action': partners_missing_fields._get_records_action(
                    name=_("Eksik Bilgili Partnerler")
                ),
            }

        # 4. Partner vergi dairesi kontrolü (e-Fatura mükellefleri için)
        einvoice_partners_missing_ref = tr_qnb_moves.partner_id.filtered(
            lambda p: getattr(p, 'l10n_tr_nilvera_customer_status', None) == 'einvoice' and not p.ref and p.country_code == 'TR'
        )

        if einvoice_partners_missing_ref:
            alerts['qnb_partners_missing_tax_office'] = {
                'level': 'danger',
                'message': _(
                    "E-Fatura mükellefi partnerlerin 'Referans' alanına vergi dairesi adı girilmelidir."
                ),
                'action_text': _("Partnerleri Görüntüle"),
                'action': einvoice_partners_missing_ref._get_records_action(
                    name=_("Vergi Dairesi Eksik Partnerler")
                ),
            }

        # 5. Şirket vergi dairesi kontrolü
        companies_missing_tax_office = tr_qnb_moves.company_id.partner_id.filtered(
            lambda p: not p.ref and p.country_code == 'TR'
        )

        if companies_missing_tax_office:
            alerts['qnb_companies_missing_tax_office'] = {
                'level': 'danger',
                'message': _(
                    "Şirket partner kaydının 'Referans' alanına vergi dairesi adı girilmelidir."
                ),
                'action_text': _("Şirketleri Görüntüle"),
                'action': companies_missing_tax_office._get_records_action(
                    name=_("Vergi Dairesi Eksik Şirketler")
                ),
            }

        # 6. Partner EDI format veya QNB durum kontrolü
        partners_invalid_status = tr_qnb_moves.filtered(
            lambda m: (
                m.partner_id.invoice_edi_format != 'ubl_tr_qnb'
                or getattr(m.partner_id, 'l10n_tr_nilvera_customer_status', None) == 'not_checked'
            )
        ).partner_id

        if partners_invalid_status:
            alerts['qnb_partners_invalid_status'] = {
                'level': 'warning',
                'message': _(
                    "Partner e-fatura formatı 'UBL TR 1.2 - QNB' olmalı veya QNB durumu kontrol edilmeli."
                ),
                'action_text': _("Partnerleri Görüntüle"),
                'action': partners_invalid_status._get_records_action(
                    name=_("Format/Durum Kontrol Edilecek Partnerler")
                ),
            }

        # 7. Negatif satır kontrolü
        moves_with_negative_lines = tr_qnb_moves.filtered(
            lambda m: m._qnb_check_negative_lines()
        )

        if moves_with_negative_lines:
            alerts['qnb_negative_lines'] = {
                'level': 'danger',
                'message': _(
                    "QNB portalı negatif miktar veya fiyat içeren satırları kabul etmez."
                ),
                'action_text': _("Faturaları Görüntüle"),
                'action': moves_with_negative_lines._get_records_action(
                    name=_("Negatif Satırlı Faturalar")
                ),
            }

        # 8. Fatura numarası format kontrolü
        moves_invalid_name = tr_qnb_moves.filtered(lambda m: not _is_valid_qnb_name(m))

        if moves_invalid_name:
            alerts['qnb_invalid_name'] = {
                'level': 'danger',
                'message': _(
                    "Fatura numarası QNB formatına uygun değil. "
                    "Format: 3 alfanumerik karakter + yıl + sıra numarası (örn: INV/2025/000001)"
                ),
                'action_text': _("Faturaları Görüntüle"),
                'action': moves_invalid_name._get_records_action(
                    name=_("Geçersiz Numaralı Faturalar")
                ),
            }

        return alerts

    # -------------------------------------------------------------------------
    # BUSINESS ACTIONS (Nilvera uyumlu)
    # -------------------------------------------------------------------------

    def _link_invoice_documents(self, invoices_data):
        """Fatura gönderim durumunu güncelle (Nilvera uyumlu)"""
        # EXTENDS 'account'
        super()._link_invoice_documents(invoices_data)
        for invoice, invoice_data in invoices_data.items():
            if invoice.company_id.country_code == 'TR' and 'tr_qnb' in invoice_data.get('extra_edis', {}):
                invoice.is_move_sent = invoice.qnb_state == 'sent'

    def _hook_invoice_document_before_pdf_report_render(self, invoice, invoice_data):
        if 'tr_qnb' in invoice_data['extra_edis']:
            if not invoice.qnb_uuid:
                invoice.qnb_uuid = str(uuid.uuid4())
            invoice_data['invoice_edi_format'] = 'ubl_tr_qnb'
        super()._hook_invoice_document_before_pdf_report_render(invoice, invoice_data)

    def _call_web_service_before_invoice_pdf_report_render(self, invoices_data):
        super()._call_web_service_before_invoice_pdf_report_render(invoices_data)

        for invoice, invoice_data in invoices_data.items():
            if 'tr_qnb' not in invoice_data['extra_edis']:
                continue

            if invoice.qnb_state not in ('not_sent', 'error'):
                invoice_data['error'] = {
                    'error_title': _("QNB e-Belgesi zaten gönderilmiş."),
                }
                continue

            if invoice_data.get('ubl_cii_xml_attachment_values'):
                xml_data = invoice_data['ubl_cii_xml_attachment_values']['raw']
            elif invoice.ubl_cii_xml_id:
                xml_data = invoice.ubl_cii_xml_id.raw
            else:
                invoice_data['error'] = {
                    'error_title': _("QNB için UBL dosyası oluşturulamadı."),
                }
                continue

            try:
                invoice._qnb_send_ubl(xml_data)
            except Exception as exc:  # noqa: BLE001
                invoice_data['error'] = {
                    'error_title': _("QNB gönderim hatası"),
                    'errors': [str(exc)],
                }
