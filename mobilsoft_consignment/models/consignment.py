# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ConsignmentDelivery(models.Model):
    """Konsinye Teslimat - Müşteriye bırakılan mal takibi"""
    _name = 'joker.consignment'
    _description = 'Konsinye Teslimat'
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Referans',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('Yeni')
    )
    
    date = fields.Date(
        string='Teslimat Tarihi',
        required=True,
        default=fields.Date.context_today
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Müşteri',
        required=True
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='Satış Temsilcisi',
        default=lambda self: self.env.user
    )
    
    warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Depo',
        required=True
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Şirket',
        required=True,
        default=lambda self: self.env.company
    )
    
    state = fields.Selection([
        ('draft', 'Taslak'),
        ('confirmed', 'Onaylandı'),
        ('delivered', 'Teslim Edildi'),
        ('partial', 'Kısmen Satıldı'),
        ('done', 'Tamamlandı'),
        ('returned', 'İade Edildi'),
        ('cancelled', 'İptal')
    ], string='Durum', default='draft')
    
    line_ids = fields.One2many(
        'joker.consignment.line',
        'consignment_id',
        string='Ürün Satırları'
    )
    
    # Ön ödeme bilgileri
    advance_amount = fields.Monetary(
        string='Ön Ödeme',
        currency_field='currency_id'
    )
    
    advance_date = fields.Date(
        string='Ön Ödeme Tarihi'
    )
    
    advance_journal_id = fields.Many2one(
        'account.journal',
        string='Ön Ödeme Kasası',
        domain=[('type', '=', 'cash')]
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Para Birimi',
        default=lambda self: self.env.company.currency_id
    )
    
    # Hesaplanan alanlar
    total_qty = fields.Float(
        string='Toplam Miktar',
        compute='_compute_totals',
        store=True
    )
    
    sold_qty = fields.Float(
        string='Satılan Miktar',
        compute='_compute_totals',
        store=True
    )
    
    returned_qty = fields.Float(
        string='İade Miktar',
        compute='_compute_totals',
        store=True
    )
    
    remaining_qty = fields.Float(
        string='Kalan Miktar',
        compute='_compute_totals',
        store=True
    )
    
    total_value = fields.Monetary(
        string='Toplam Değer',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id'
    )
    
    notes = fields.Text(string='Notlar')
    
    @api.depends('line_ids.quantity', 'line_ids.sold_qty', 'line_ids.returned_qty', 'line_ids.subtotal')
    def _compute_totals(self):
        for record in self:
            record.total_qty = sum(record.line_ids.mapped('quantity'))
            record.sold_qty = sum(record.line_ids.mapped('sold_qty'))
            record.returned_qty = sum(record.line_ids.mapped('returned_qty'))
            record.remaining_qty = record.total_qty - record.sold_qty - record.returned_qty
            record.total_value = sum(record.line_ids.mapped('subtotal'))
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('Yeni')) == _('Yeni'):
                vals['name'] = self.env['ir.sequence'].next_by_code('joker.consignment') or _('Yeni')
        return super().create(vals_list)
    
    def action_confirm(self):
        """Konsinye teslimatı onayla"""
        for record in self:
            if not record.line_ids:
                raise UserError(_('En az bir ürün satırı eklemelisiniz.'))
            record.state = 'confirmed'
    
    def action_deliver(self):
        """Ürünleri teslim et - stok çıkışı yap"""
        for record in self:
            # TODO: Stok hareketi oluştur (konsinye lokasyona)
            record.state = 'delivered'
    
    def action_create_invoice(self):
        """Satılan ürünler için fatura oluştur"""
        self.ensure_one()
        # Satılmış ama faturalanmamış satırları bul
        lines_to_invoice = self.line_ids.filtered(
            lambda l: l.sold_qty > l.invoiced_qty
        )
        if not lines_to_invoice:
            raise UserError(_('Faturalanacak satılmış ürün bulunamadı.'))
        
        # Fatura oluştur
        invoice_vals = {
            'partner_id': self.partner_id.id,
            'move_type': 'out_invoice',
            'invoice_date': fields.Date.context_today(self),
            'invoice_origin': self.name,
            'invoice_line_ids': [(0, 0, {
                'product_id': line.product_id.id,
                'quantity': line.sold_qty - line.invoiced_qty,
                'price_unit': line.price_unit,
            }) for line in lines_to_invoice]
        }
        invoice = self.env['account.move'].create(invoice_vals)
        
        # Faturalanan miktarları güncelle
        for line in lines_to_invoice:
            line.invoiced_qty = line.sold_qty
        
        # Durumu güncelle
        if self.remaining_qty == 0:
            self.state = 'done'
        else:
            self.state = 'partial'
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Fatura'),
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
        }
    
    def action_return(self):
        """İade işlemi"""
        for record in self:
            # TODO: İade için wizard aç
            record.state = 'returned'
    
    def action_cancel(self):
        """İptal et"""
        for record in self:
            record.state = 'cancelled'
    
    def action_draft(self):
        """Taslağa döndür"""
        for record in self:
            record.state = 'draft'


class ConsignmentLine(models.Model):
    """Konsinye Teslimat Satırı"""
    _name = 'joker.consignment.line'
    _description = 'Konsinye Teslimat Satırı'
    
    consignment_id = fields.Many2one(
        'joker.consignment',
        string='Konsinye Teslimat',
        required=True,
        ondelete='cascade'
    )
    
    product_id = fields.Many2one(
        'product.product',
        string='Ürün',
        required=True
    )
    
    quantity = fields.Float(
        string='Teslim Miktar',
        required=True,
        default=1.0
    )
    
    uom_id = fields.Many2one(
        'uom.uom',
        string='Birim',
        related='product_id.uom_id'
    )
    
    price_unit = fields.Float(
        string='Birim Fiyat',
        required=True
    )
    
    sold_qty = fields.Float(
        string='Satılan Miktar',
        default=0.0
    )
    
    returned_qty = fields.Float(
        string='İade Miktar',
        default=0.0
    )
    
    invoiced_qty = fields.Float(
        string='Faturalanan Miktar',
        default=0.0
    )
    
    remaining_qty = fields.Float(
        string='Kalan Miktar',
        compute='_compute_remaining'
    )
    
    subtotal = fields.Float(
        string='Toplam',
        compute='_compute_subtotal',
        store=True
    )
    
    currency_id = fields.Many2one(
        related='consignment_id.currency_id'
    )
    
    @api.depends('quantity', 'sold_qty', 'returned_qty')
    def _compute_remaining(self):
        for line in self:
            line.remaining_qty = line.quantity - line.sold_qty - line.returned_qty
    
    @api.depends('quantity', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.price_unit = self.product_id.list_price
