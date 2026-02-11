# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class QnbSendInvoiceWizard(models.TransientModel):
    _name = 'qnb.send.invoice.wizard'
    _description = 'e-Belge Gönderimi Sihirbazı'

    move_id = fields.Many2one(
        'account.move',
        string='Fatura',
        required=True
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Müşteri',
        related='move_id.partner_id'
    )

    document_type = fields.Selection([
        ('efatura', 'e-Fatura'),
        ('earsiv', 'e-Arşiv')
    ], string='Belge Türü', required=True, default='efatura')

    scenario = fields.Selection([
        ('TEMELFATURA', 'Temel Fatura'),
        ('TICARIFATURA', 'Ticari Fatura')
    ], string='Senaryo', default='TEMELFATURA')

    invoice_type = fields.Selection([
        ('SATIS', 'Satış'),
        ('IADE', 'İade'),
        ('ISTISNA', 'İstisna'),
        ('OZELMATRAH', 'Özel Matrah'),
        ('TEVKIFAT', 'Tevkifat')
    ], string='Fatura Tipi', default='SATIS')

    is_partner_efatura = fields.Boolean(
        string='Müşteri e-Fatura Kayıtlı',
        compute='_compute_is_partner_efatura'
    )

    note = fields.Text(string='Not')

    @api.depends('partner_id', 'partner_id.l10n_tr_nilvera_customer_status')
    def _compute_is_partner_efatura(self):
        for r in self:
            r.is_partner_efatura = getattr(r.partner_id, 'l10n_tr_nilvera_customer_status', None) == 'einvoice'

    @api.onchange('document_type')
    def _onchange_document_type(self):
        if self.document_type == 'efatura' and not self.is_partner_efatura:
            return {
                'warning': {
                    'title': _('Uyarı'),
                    'message': _('Bu müşteri e-Fatura sistemine kayıtlı değil. e-Arşiv kullanmanız önerilir.')
                }
            }

    def action_send(self):
        """Belgeyi gönder"""
        self.ensure_one()

        if not self.move_id.state == 'posted':
            raise UserError(_("Sadece onaylanmış faturalar gönderilebilir!"))

        if self.document_type == 'efatura':
            if getattr(self.partner_id, 'l10n_tr_nilvera_customer_status', None) != 'einvoice':
                raise UserError(_("Bu müşteri e-Fatura sistemine kayıtlı değil!"))
            return self.move_id.action_send_efatura()
        else:
            return self.move_id.action_send_earsiv()


class QnbRejectWizard(models.TransientModel):
    _name = 'qnb.reject.wizard'
    _description = 'Belge Reddetme Sihirbazı'

    document_id = fields.Many2one(
        'qnb.document',
        string='Belge',
        required=True
    )
    reason = fields.Text(
        string='Red Sebebi',
        required=True,
        help='Belgeyi neden reddettiğinizi açıklayın'
    )

    def action_reject(self):
        """Belgeyi reddet"""
        self.ensure_one()

        if not self.reason:
            raise UserError(_("Red sebebi zorunludur!"))

        api_client = self.env['qnb.api.client']
        result = api_client.reject_invoice(
            self.document_id.ettn,
            self.reason,
            self.document_id.company_id
        )

        if result.get('success'):
            self.document_id.write({
                'state': 'rejected',
                'rejection_reason': self.reason
            })
            self.document_id._create_history('rejected', f'Belge reddedildi: {self.reason}')

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Belge Reddedildi',
                    'message': 'Belge başarıyla reddedildi.',
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            raise UserError(_("Red hatası: %s") % result.get('message'))
