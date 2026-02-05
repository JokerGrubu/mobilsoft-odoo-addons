# -*- coding: utf-8 -*-

from odoo import models
from odoo.exceptions import UserError
from odoo.addons.account_edi_ubl_cii.models.account_edi_xml_ubl_21 import AccountEdiXmlUbl_21


class AccountEdiXmlUblTrQnb(models.AbstractModel):
    _name = "account.edi.xml.ubl.tr.qnb"
    _inherit = "account.edi.xml.ubl.tr"
    _description = "UBL-TR 1.2 (QNB)"

    def _add_invoice_header_nodes(self, document_node, vals):
        AccountEdiXmlUbl_21._add_invoice_header_nodes(self, document_node, vals)
        invoice = vals['invoice']

        if invoice.country_code != 'TR':
            return

        if invoice.partner_id.qnb_customer_status == 'not_checked':
            invoice.partner_id._check_qnb_customer()

        if invoice._qnb_check_negative_lines():
            raise UserError(self.env._("QNB portalı negatif miktar veya negatif fiyat içeren satırları kabul etmez."))

        _, parts = invoice._get_sequence_format_param(invoice.name)
        prefix, year, number = parts['prefix1'][:3], parts['year'], str(parts['seq']).zfill(9)
        invoice_id = f"{prefix.upper()}{year}{number}"

        is_einvoice = invoice.partner_id.qnb_customer_status == 'einvoice'
        profile_id = invoice.company_id.qnb_efatura_scenario if is_einvoice else 'EARSIVFATURA'

        document_node.update({
            'cbc:CustomizationID': {'_text': 'TR1.2'},
            'cbc:ProfileID': {'_text': profile_id},
            'cbc:ID': {'_text': invoice_id},
            'cbc:CopyIndicator': {'_text': 'false'},
            'cbc:UUID': {'_text': invoice.qnb_uuid or invoice_id},
            'cbc:DueDate': None,
            'cbc:InvoiceTypeCode': {'_text': 'SATIS'} if vals['document_type'] == 'invoice' else None,
            'cbc:CreditNoteTypeCode': {'_text': 'IADE'} if vals['document_type'] == 'credit_note' else None,
            'cbc:PricingCurrencyCode': {'_text': invoice.currency_id.name.upper()}
                if vals['currency_id'] != vals['company_currency_id'] else None,
            'cbc:LineCountNumeric': {'_text': len(invoice.line_ids)},
            'cbc:BuyerReference': None,
        })

        if invoice.partner_id.qnb_customer_status == 'earchive':
            document_node['cac:AdditionalDocumentReference'] = {
                'cbc:ID': {'_text': invoice.company_id.qnb_earsiv_send_type or 'ELEKTRONIK'},
                'cbc:IssueDate': {'_text': invoice.invoice_date},
                'cbc:DocumentTypeCode': {'_text': 'SEND_TYPE'},
            }

        document_node['cbc:Note'] = [
            document_node.get('cbc:Note'),
            {'_text': self._l10n_tr_get_amount_integer_partn_text_note(invoice.amount_residual_signed, self.env.ref('base.TRY')), 'note_attrs': {}}
        ]
        if invoice.currency_id.name != 'TRY':
            document_node['cbc:Note'].append({'_text': self._l10n_tr_get_amount_integer_partn_text_note(invoice.amount_residual, invoice.currency_id), 'note_attrs': {}})
            document_node['cbc:Note'].append({'_text': self._l10n_tr_get_invoice_currency_exchange_rate(invoice)})
