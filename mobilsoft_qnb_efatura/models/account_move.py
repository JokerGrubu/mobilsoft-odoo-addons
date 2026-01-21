# -*- coding: utf-8 -*-

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
        """e-Belgeleri görüntüle"""
        self.ensure_one()

        action = self.env['ir.actions.act_window']._for_xml_id('mobilsoft_qnb_efatura.action_qnb_document')
        action['domain'] = [('move_id', '=', self.id)]
        action['context'] = {'default_move_id': self.id, 'default_partner_id': self.partner_id.id}

        if len(self.qnb_document_ids) == 1:
            action['views'] = [(False, 'form')]
            action['res_id'] = self.qnb_document_ids.id

        return action

    def action_send_efatura(self):
        """e-Fatura gönder"""
        self.ensure_one()

        if self.state != 'posted':
            raise UserError(_("Sadece onaylanmış faturalar gönderilebilir!"))

        if self.qnb_state not in ('not_sent', 'error'):
            raise UserError(_("Bu fatura zaten gönderilmiş veya işlem bekliyor!"))

        # Önce partner kontrolü
        if not self.partner_id.vat:
            raise UserError(_("Müşteri VKN/TCKN bilgisi eksik!"))

        # e-Fatura kaydı kontrolü
        if not self.partner_id.is_efatura_registered:
            # e-Arşiv'e yönlendir
            return self.action_send_earsiv()

        # e-Belge kaydı oluştur
        document = self.env['qnb.document'].create({
            'name': self.name,
            'move_id': self.id,
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
            'document_type': 'efatura',
            'direction': 'outgoing',
            'document_date': self.invoice_date,
            'amount_untaxed': self.amount_untaxed,
            'amount_tax': self.amount_tax,
            'amount_total': self.amount_total,
            'currency_id': self.currency_id.id,
            'scenario': self.company_id.qnb_efatura_scenario,
        })

        # Gönder
        document.action_send()

        # Fatura durumunu güncelle
        self.write({
            'qnb_state': document.state,
            'qnb_ettn': document.ettn
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'e-Fatura',
                'message': f"Fatura başarıyla gönderildi.\nETTN: {document.ettn}",
                'type': 'success',
                'sticky': False,
            }
        }

    def action_send_earsiv(self):
        """e-Arşiv gönder"""
        self.ensure_one()

        if self.state != 'posted':
            raise UserError(_("Sadece onaylanmış faturalar gönderilebilir!"))

        if self.qnb_state not in ('not_sent', 'error'):
            raise UserError(_("Bu fatura zaten gönderilmiş veya işlem bekliyor!"))

        # e-Belge kaydı oluştur
        document = self.env['qnb.document'].create({
            'name': self.name,
            'move_id': self.id,
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
            'document_type': 'earsiv',
            'direction': 'outgoing',
            'document_date': self.invoice_date,
            'amount_untaxed': self.amount_untaxed,
            'amount_tax': self.amount_tax,
            'amount_total': self.amount_total,
            'currency_id': self.currency_id.id,
        })

        # Gönder
        document.action_send()

        # Fatura durumunu güncelle
        self.write({
            'qnb_state': document.state,
            'qnb_ettn': document.ettn
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'e-Arşiv',
                'message': f"e-Arşiv fatura başarıyla gönderildi.\nETTN: {document.ettn}",
                'type': 'success',
                'sticky': False,
            }
        }

    def action_check_qnb_status(self):
        """e-Belge durumunu kontrol et"""
        self.ensure_one()

        if not self.qnb_document_ids:
            raise UserError(_("Bu fatura için e-Belge kaydı bulunamadı!"))

        document = self.qnb_document_ids[0]
        result = document.action_check_status()

        # Fatura durumunu güncelle
        self.qnb_state = document.state

        return result

    def action_open_send_wizard(self):
        """e-Belge gönderim sihirbazını aç"""
        self.ensure_one()

        return {
            'name': _('e-Belge Gönder'),
            'type': 'ir.actions.act_window',
            'res_model': 'qnb.send.invoice.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_move_id': self.id,
                'default_partner_id': self.partner_id.id,
                'default_document_type': self.qnb_document_type,
            }
        }

    @api.model
    def cron_check_qnb_status(self):
        """Zamanlanmış görev: Bekleyen e-Belgelerin durumunu kontrol et"""
        invoices = self.search([
            ('qnb_state', 'in', ('sent', 'sending', 'delivered')),
            ('qnb_ettn', '!=', False)
        ], limit=50)

        for invoice in invoices:
            try:
                invoice.action_check_qnb_status()
            except Exception:
                continue

        return True
