from odoo import models, fields, api


class MobilsoftChequePromissory(models.Model):
    _name = 'mobilsoft.cheque.promissory'
    _description = 'Çek / Senet'
    _order = 'maturity_date'

    name = fields.Char(string='Referans', required=True, copy=False,
                       default=lambda self: self.env['ir.sequence'].next_by_code('cheque.promissory'))
    type = fields.Selection([
        ('cheque', 'Çek'),
        ('promissory', 'Senet'),
    ], string='Tür', required=True, default='cheque')
    direction = fields.Selection([
        ('received', 'Alınan'),
        ('given', 'Verilen'),
    ], string='Yön', required=True, default='received')
    partner_id = fields.Many2one('res.partner', string='Cari', required=True)
    amount = fields.Monetary(string='Tutar', currency_field='currency_id', required=True)
    currency_id = fields.Many2one('res.currency', string='Para Birimi',
                                  default=lambda self: self.env.company.currency_id)
    bank_id = fields.Many2one('res.bank', string='Banka')
    bank_branch = fields.Char(string='Şube')
    account_number = fields.Char(string='Hesap No')
    maturity_date = fields.Date(string='Vade Tarihi', required=True)
    collection_date = fields.Date(string='Tahsilat Tarihi')
    notes = fields.Text(string='Notlar')
    state = fields.Selection([
        ('portfolio', 'Portföyde'),
        ('collected', 'Tahsil Edildi'),
        ('paid', 'Ödendi'),
        ('endorsed', 'Ciro Edildi'),
        ('bounced', 'Protestolu'),
        ('cancelled', 'İptal'),
    ], string='Durum', default='portfolio', required=True)
    company_id = fields.Many2one('res.company', string='Şirket',
                                 default=lambda self: self.env.company)
    days_overdue = fields.Integer(string='Gecikme Günü', compute='_compute_days_overdue')
    is_overdue = fields.Boolean(string='Vadesi Geçmiş', compute='_compute_days_overdue', store=True)

    @api.depends('maturity_date', 'state')
    def _compute_days_overdue(self):
        from datetime import date
        today = date.today()
        for rec in self:
            if rec.maturity_date and rec.state == 'portfolio':
                delta = (today - rec.maturity_date).days
                rec.days_overdue = max(0, delta)
                rec.is_overdue = delta > 0
            else:
                rec.days_overdue = 0
                rec.is_overdue = False
