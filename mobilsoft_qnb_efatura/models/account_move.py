# -*- coding: utf-8 -*-

import uuid
from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    # QNB e-Belge Bilgileri
    qnb_document_ids = fields.One2many(
        'qnb.document',
        'move_id',
        string='e-Belgeler'
    )
    qnb_document_count = fields.Integer(
        string='e-Belge Sayısı',
        compute='_compute_qnb_document_count'
    )

    qnb_state = fields.Selection([
        ('not_sent', 'Gönderilmedi'),
        ('sending', 'Gönderiliyor'),
        ('sent', 'Gönderildi'),
        ('delivered', 'Teslim Edildi'),
        ('accepted', 'Kabul Edildi'),
        ('rejected', 'Reddedildi'),
        ('error', 'Hata')
    ], string='e-Belge Durumu', default='not_sent', tracking=True)

    qnb_ettn = fields.Char(
        string='ETTN',
        help='Evrensel Tekil Tanımlayıcı Numara',
        copy=False
    )
    qnb_uuid = fields.Char(
        string='QNB UUID',
        copy=False
    )
    qnb_document_type = fields.Selection([
        ('efatura', 'e-Fatura'),
        ('earsiv', 'e-Arşiv'),
        ('manual', 'Manuel')
    ], string='e-Belge Türü', compute='_compute_qnb_document_type', store=True)

    @api.depends('qnb_document_ids')
    def _compute_qnb_document_count(self):
        for move in self:
            move.qnb_document_count = len(move.qnb_document_ids)

    @api.depends('partner_id', 'partner_id.is_efatura_registered')
    def _compute_qnb_document_type(self):
        for move in self:
            if move.move_type in ('out_invoice', 'out_refund'):
                if move.partner_id.is_efatura_registered:
                    move.qnb_document_type = 'efatura'
                else:
                    move.qnb_document_type = 'earsiv'
            else:
                move.qnb_document_type = 'manual'

    def action_view_qnb_documents(self):
        self.ensure_one()
        raise UserError(_("QNB e-Belge ekranı devre dışı. Lütfen standart gönderim ekranını kullanın."))

    def action_send_efatura(self):
        self.ensure_one()
        raise UserError(_("QNB gönderimi artık standart EDI akışı üzerinden yapılmaktadır. Lütfen gönderim ekranını kullanın."))

    def action_send_earsiv(self):
        self.ensure_one()
        raise UserError(_("QNB gönderimi artık standart EDI akışı üzerinden yapılmaktadır. Lütfen gönderim ekranını kullanın."))

    def action_check_qnb_status(self):
        self.ensure_one()
        if not self.qnb_ettn:
            raise UserError(_("ETTN bilgisi bulunamadı!"))
        status_result = self._qnb_update_status_from_api()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'QNB Durum',
                'message': status_result.get('status_description') or status_result.get('status') or 'OK',
                'type': 'success' if status_result.get('success') else 'warning',
                'sticky': False,
            }
        }

    def action_open_send_wizard(self):
        self.ensure_one()
        raise UserError(_("QNB gönderimi standart EDI akışına taşındı."))

    @api.model
    def cron_check_qnb_status(self):
        return self._cron_qnb_get_invoice_status()

    def _post(self, soft=True):
        for move in self:
            if move.country_code == 'TR' and not move.qnb_uuid:
                move.qnb_uuid = str(uuid.uuid4())
        return super()._post(soft=soft)

    def _qnb_check_negative_lines(self):
        return any(
            line.display_type not in {'line_note', 'line_section'}
            and (line.quantity < 0 or line.price_unit < 0)
            for line in self.invoice_line_ids
        )

    def _qnb_is_einvoice(self):
        self.ensure_one()
        if not self.partner_id.vat:
            return False
        if self.partner_id.qnb_customer_status == 'not_checked':
            self.partner_id._check_qnb_customer()
        return self.partner_id.qnb_customer_status == 'einvoice'

    def _qnb_get_partner_vkn(self):
        self.ensure_one()
        if not self.partner_id.vat:
            raise UserError(_("Müşteri VKN/TCKN bilgisi eksik!"))
        digits = ''.join(filter(str.isdigit, self.partner_id.vat))
        if not digits:
            raise UserError(_("Müşteri VKN/TCKN bilgisi eksik!"))
        return digits

    def _qnb_get_send_document_type(self):
        return 'FATURA_UBL' if self._qnb_is_einvoice() else 'EARSIV_FATURA'

    def _qnb_get_status_document_type(self):
        if self.qnb_document_type == 'efatura':
            return 'EFATURA'
        if self.qnb_document_type == 'earsiv':
            return 'EARSIV'
        return 'EFATURA' if self._qnb_is_einvoice() else 'EARSIV'

    def _qnb_send_ubl(self, xml_data):
        self.ensure_one()
        if self.state != 'posted':
            raise UserError(_("Sadece onaylanmış faturalar gönderilebilir!"))
        if self.qnb_state not in ('not_sent', 'error'):
            raise UserError(_("Bu fatura zaten gönderilmiş veya işlem bekliyor!"))
        if not self.qnb_uuid:
            self.qnb_uuid = str(uuid.uuid4())

        api_client = self.env['qnb.api.client']
        vkn = self._qnb_get_partner_vkn()

        if self._qnb_is_einvoice():
            result = api_client.send_invoice(
                xml_data,
                self.name,
                vkn,
                self.company_id,
                document_type='FATURA_UBL'
            )
        else:
            result = api_client.send_earchive_invoice(
                xml_data,
                self.name,
                self.company_id
            )

        if result.get('success'):
            self.write({
                'qnb_state': 'sent',
                'qnb_ettn': result.get('ettn'),
            })
            self.message_post(body=_("QNB e-Belgesi başarıyla gönderildi."))
            return result

        self.write({'qnb_state': 'error'})
        raise UserError(result.get('message', 'QNB gönderim hatası'))

    def _qnb_update_status_from_api(self):
        self.ensure_one()
        api_client = self.env['qnb.api.client']
        result = api_client.get_document_status(
            self.qnb_ettn,
            self._qnb_get_status_document_type(),
            self.company_id
        )

        if result.get('success'):
            status = (result.get('status') or '').upper()
            state_map = {
                'GONDERILDI': 'sent',
                'TESLIM_ALINDI': 'delivered',
                'KABUL': 'accepted',
                'RED': 'rejected',
                'HATA': 'error',
                'IPTAL': 'rejected',
            }
            new_state = state_map.get(status)
            if new_state and new_state != self.qnb_state:
                self.write({'qnb_state': new_state})
        return result

    def _qnb_add_pdf_to_invoice(self, pdf_content):
        self.ensure_one()
        if not pdf_content:
            return
        if isinstance(pdf_content, str):
            pdf_content = pdf_content.encode('utf-8')
        attachment = self.env['ir.attachment'].create({
            'name': f'{self.name}.pdf',
            'res_id': self.id,
            'res_model': 'account.move',
            'raw': pdf_content,
            'type': 'binary',
            'mimetype': 'application/pdf',
        })
        self.message_main_attachment_id = attachment
        self.with_context(no_new_invoice=True).message_post(attachment_ids=attachment.ids)

    def _qnb_fetch_outgoing_pdf(self):
        self.ensure_one()
        api_client = self.env['qnb.api.client']
        result = api_client.download_outgoing_document(
            self.qnb_ettn,
            document_type=self._qnb_get_send_document_type(),
            company=self.company_id,
            format_type='PDF'
        )
        if result.get('success'):
            self._qnb_add_pdf_to_invoice(result.get('content'))

    def _qnb_get_purchase_journal(self, company):
        return self.env['account.journal'].search([
            ('type', '=', 'purchase'),
            ('company_id', '=', company.id),
        ], limit=1)

    def _qnb_get_last_fetch_date(self, company):
        param_key = f"qnb_incoming_last_fetch_date.{company.id}"
        last_fetched_date = self.env['ir.config_parameter'].sudo().get_param(param_key)
        if not last_fetched_date:
            last_fetched_date = (fields.Date.today() - relativedelta(months=1)).strftime("%Y-%m-%d")
            self.env['ir.config_parameter'].sudo().set_param(param_key, last_fetched_date)
        return last_fetched_date

    def _qnb_set_last_fetch_date(self, company, value):
        param_key = f"qnb_incoming_last_fetch_date.{company.id}"
        self.env['ir.config_parameter'].sudo().set_param(param_key, value)

    def _qnb_fetch_incoming_documents(self):
        company = self.env.company
        api_client = self.env['qnb.api.client']
        start_date = self._qnb_get_last_fetch_date(company)
        end_date = fields.Date.today().strftime("%Y-%m-%d")

        result = api_client.get_incoming_documents(start_date, end_date, document_type='EFATURA', company=company)
        if not result.get('success'):
            return

        journal = self._qnb_get_purchase_journal(company)
        if not journal:
            return

        for doc in result.get('documents', []):
            ettn = doc.get('ettn')
            if not ettn:
                continue
            if self.search_count([('qnb_ettn', '=', ettn), ('company_id', '=', company.id)]) > 0:
                continue

            download = api_client.download_incoming_document(ettn, document_type='EFATURA', company=company)
            if not download.get('success'):
                continue

            content = download.get('content')
            if isinstance(content, str):
                content = content.encode('utf-8')

            attachment = self.env['ir.attachment'].create({
                'name': f'{ettn}.xml',
                'raw': content,
                'type': 'binary',
                'mimetype': 'application/xml',
            })

            move = journal.with_context(
                default_move_type='in_invoice',
                default_company_id=company.id,
                default_qnb_ettn=ettn,
                default_qnb_state='delivered',
            )._create_document_from_attachment(attachment.id)
            move.message_post(body=_("QNB belgesi alındı."))

        self._qnb_set_last_fetch_date(company, end_date)

    def _cron_qnb_get_new_incoming_documents(self):
        companies = self.env['res.company'].search([('qnb_enabled', '=', True)])
        for company in companies:
            self.with_company(company)._qnb_fetch_incoming_documents()

    def _cron_qnb_get_invoice_status(self):
        invoices_to_update = self.search([
            ('qnb_state', 'in', ['sent', 'sending', 'delivered']),
            ('qnb_ettn', '!=', False),
        ])
        for invoice in invoices_to_update:
            invoice._qnb_update_status_from_api()

    def _cron_qnb_get_sale_pdf(self, batch_size=100):
        invoices = self.search([
            ('qnb_state', 'in', ['sent', 'delivered', 'accepted']),
            ('qnb_ettn', '!=', False),
            ('move_type', 'in', ['out_invoice', 'out_refund']),
        ], limit=batch_size)
        invoices_to_fetch = invoices.filtered(lambda m: m.message_main_attachment_id == m.invoice_pdf_report_id)
        for invoice in invoices_to_fetch:
            invoice._qnb_fetch_outgoing_pdf()
