# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import date


class ChequePromissory(models.Model):
    """
    Çek & Senet Yönetimi
    Türkiye'de çok önemli bir ön muhasebe özelliği
    """
    _name = 'mobilsoft.cheque.promissory'
    _description = 'Çek & Senet'
    _order = 'maturity_date asc'
    
    name = fields.Char(
        string='Çek/Senet No',
        required=True,
        index=True,
    )
    
    type = fields.Selection(
        [
            ('cheque', 'Çek'),
            ('promissory', 'Senet'),
        ],
        string='Tür',
        required=True,
        default='cheque',
    )
    
    direction = fields.Selection(
        [
            ('received', 'Alınan'),
            ('given', 'Verilen'),
        ],
        string='Yön',
        required=True,
        default='received',
    )
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Cari',
        required=True,
        index=True,
    )
    
    amount = fields.Monetary(
        string='Tutar',
        currency_field='currency_id',
        required=True,
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Para Birimi',
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    
    bank_id = fields.Many2one(
        'res.bank',
        string='Banka',
    )
    
    bank_branch = fields.Char(
        string='Banka Şubesi',
    )
    
    account_number = fields.Char(
        string='Hesap No',
    )
    
    maturity_date = fields.Date(
        string='Vade Tarihi',
        required=True,
        index=True,
    )
    
    state = fields.Selection(
        [
            ('portfolio', 'Portföy'),
            ('collected', 'Tahsil Edildi'),
            ('paid', 'Ödendi'),
            ('endorsed', 'Ciro Edildi'),
            ('bounced', 'Karşılıksız'),
            ('cancelled', 'İptal'),
        ],
        string='Durum',
        default='portfolio',
        required=True,
        index=True,
    )
    
    collection_date = fields.Date(
        string='Tahsil/Ödeme Tarihi',
    )
    
    notes = fields.Text(
        string='Notlar',
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Şirket',
        default=lambda self: self.env.company,
        required=True,
    )
    
    # Computed
    is_overdue = fields.Boolean(
        string='Vadesi Geçmiş',
        compute='_compute_is_overdue',
        store=True,
    )
    
    days_overdue = fields.Integer(
        string='Gecikme Günü',
        compute='_compute_is_overdue',
        store=True,
    )
    
    @api.depends('maturity_date', 'state')
    def _compute_is_overdue(self):
        """Vade kontrolü"""
        today = date.today()
        for record in self:
            if record.maturity_date and record.state in ('portfolio', 'endorsed'):
                record.is_overdue = record.maturity_date < today
                if record.is_overdue:
                    record.days_overdue = (today - record.maturity_date).days
                else:
                    record.days_overdue = 0
            else:
                record.is_overdue = False
                record.days_overdue = 0
    
    def action_collect(self):
        """Tahsil/Ödeme işlemi"""
        self.ensure_one()
        self.write({
            'state': 'collected' if self.direction == 'received' else 'paid',
            'collection_date': date.today(),
        })
    
    def action_bounce(self):
        """Karşılıksız işaretle"""
        self.ensure_one()
        self.write({
            'state': 'bounced',
        })
    
    def action_endorse(self):
        """Ciro et"""
        self.ensure_one()
        self.write({
            'state': 'endorsed',
        })
