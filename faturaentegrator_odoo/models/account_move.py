from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    fe_invoice_id = fields.Many2one('fe.invoice', string='FE Fatura Kaydı', compute='_compute_fe_invoice_id', store=False, readonly=True)
    fe_external_id = fields.Char(string='Fatura Entegratör Fatura ID', related='fe_invoice_id.external_id', store=False, readonly=True)
    fe_invoice_url = fields.Char(string='FE Fatura Linki', related='fe_invoice_id.fe_invoice_url', store=False, readonly=True)
    fe_pdf_url = fields.Char(string='FE PDF URL', related='fe_invoice_id.pdf_url', store=False, readonly=True)
    fe_pdf_attachment_id = fields.Many2one('ir.attachment', string='FE PDF Dosyası', related='fe_invoice_id.pdf_attachment_id', store=False, readonly=True)
    fe_state = fields.Selection(
        selection=[
            ('draft', 'Taslak'),
            ('sent', 'Gönderildi'),
            ('formalized', 'Resmileştirildi'),
            ('cancelled', 'İptal Edildi'),
            ('rejected', 'Reddedildi'),
        ],
        string='FE Durumu',
        related='fe_invoice_id.fe_status',
        store=False,
        readonly=True
    )
    
    def _compute_fe_invoice_id(self):
        """Faturaya bağlı fe.invoice kaydını bul"""
        for move in self:
            fe_invoice = self.env['fe.invoice'].search([
                ('account_move_id', '=', move.id)
            ], limit=1, order='create_date desc')
            move.fe_invoice_id = fe_invoice.id if fe_invoice else False
    
    def action_view_fe_invoice(self):
        """FE Fatura kaydına git"""
        self.ensure_one()
        if not self.fe_invoice_id:
            raise UserError(_('Bu fatura için FE fatura kaydı bulunamadı.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('FE Fatura'),
            'res_model': 'fe.invoice',
            'res_id': self.fe_invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_view_fe_pdf(self):
        """FE PDF'i göster - PDF URL'den direkt indirir"""
        self.ensure_one()
        if self.fe_pdf_url:
            # PDF URL varsa, direkt linke git
            return {
                'type': 'ir.actions.act_url',
                'url': self.fe_pdf_url,
                'target': 'new',
            }
        else:
            raise UserError(_('PDF URL bulunamadı. Fatura henüz formalize edilmemiş olabilir.'))
    
    def _get_sale_order_from_move(self, move):
        """account.move'dan sale.order'ı bul"""
        # invoice_line_ids üzerinden sale.order.line'a bağlan
        for line in move.invoice_line_ids:
            if line.sale_line_ids:
                return line.sale_line_ids[0].order_id
        # invoice_origin üzerinden dene
        if move.invoice_origin:
            return self.env['sale.order'].search([('name', '=', move.invoice_origin)], limit=1)
        return None
    
    def action_send_to_fe(self):
        """Wizard ile FE'e gönder"""
        self.ensure_one()
        if self.move_type not in ('out_invoice', 'out_refund'):
            raise UserError(_('Sadece satış faturaları gönderilebilir.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Fatura Entegratör Gönder'),
            'res_model': 'fe.send.invoice.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_move_id': self.id,
                'default_company_id': self.company_id.id,
            },
        }

