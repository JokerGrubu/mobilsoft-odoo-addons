# -*- coding: utf-8 -*-

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

    def _get_all_extra_edis(self) -> dict:
        res = super()._get_all_extra_edis()
        res.update({'tr_qnb': {'label': _("by QNB e-Solutions"), 'is_applicable': self._is_tr_qnb_applicable}})
        return res

    def _hook_invoice_document_before_pdf_report_render(self, invoice, invoice_data):
        if 'tr_qnb' in invoice_data['extra_edis']:
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
