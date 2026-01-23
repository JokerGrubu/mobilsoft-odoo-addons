from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    fe_invoice_id = fields.Many2one('fe.invoice', string='FE Fatura Kaydı', compute='_compute_fe_invoice_id', store=False, readonly=True)
    fe_external_id = fields.Char(string='Fatura Entegratör Sipariş ID', related='fe_invoice_id.external_id', store=False, readonly=True)
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
        """Siparişe bağlı fe.invoice kaydını bul"""
        for order in self:
            fe_invoice = self.env['fe.invoice'].search([
                ('sale_order_id', '=', order.id)
            ], limit=1, order='create_date desc')
            order.fe_invoice_id = fe_invoice.id if fe_invoice else False
    
    def action_view_fe_invoice(self):
        """FE Fatura kaydına git"""
        self.ensure_one()
        if not self.fe_invoice_id:
            raise UserError(_('Bu sipariş için FE fatura kaydı bulunamadı.'))
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

    def _build_fe_order_payload(self) -> dict:
        self.ensure_one()
        partner = self.partner_invoice_id or self.partner_id
        lines = []
        for line in self.order_line.filtered(lambda l: not l.display_type):
            lines.append({
                'name': line.name,
                'sku': line.product_id.default_code or '',
                'quantity': line.product_uom_qty,
                'price_unit': line.price_unit,
                'taxes': [t.amount for t in line.tax_id],
            })
        payload = {
            'order': {
                'number': self.name,
                'date_order': fields.Datetime.to_string(self.date_order),
                'currency': self.currency_id.name,
                'amount_total': self.amount_total,
                'amount_untaxed': self.amount_untaxed,
                'amount_tax': self.amount_tax,
            },
            'customer': {
                'name': partner.name,
                'vat': partner.vat or '',
                'email': partner.email or '',
                'phone': partner.phone or partner.mobile or '',
                'street': partner.street or '',
                'city': partner.city or '',
                'zip': partner.zip or '',
                'country': partner.country_id and partner.country_id.code or '',
            },
            'lines': lines,
        }
        return payload

    def action_send_to_fe(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Fatura Entegratör Gönder'),
            'res_model': 'fe.send.order.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_order_id': self.id,
                'default_company_id': self.company_id.id,
            },
        }

