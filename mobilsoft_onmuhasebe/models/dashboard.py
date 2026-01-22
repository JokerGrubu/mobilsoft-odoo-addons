# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MobilsoftDashboard(models.TransientModel):
    """
    Dashboard Metrics - Computed fields için geçici model
    """
    _name = 'mobilsoft.dashboard'
    _description = 'Ön Muhasebe Dashboard'
    
    # Top Cards
    total_cash = fields.Monetary(
        string='Toplam Kasa',
        compute='_compute_totals',
        currency_field='currency_id',
    )
    
    total_bank = fields.Monetary(
        string='Toplam Banka',
        compute='_compute_totals',
        currency_field='currency_id',
    )
    
    total_receivable = fields.Monetary(
        string='Toplam Alacaklar',
        compute='_compute_totals',
        currency_field='currency_id',
    )
    
    total_payable = fields.Monetary(
        string='Toplam Borçlar',
        compute='_compute_totals',
        currency_field='currency_id',
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )
    
    @api.model
    def default_get(self, fields_list):
        """Default değerleri ayarla ve compute et"""
        res = super().default_get(fields_list)
        # Currency'yi ayarla
        if 'currency_id' in fields_list:
            res['currency_id'] = self.env.company.currency_id.id
        return res
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create sonrası compute et"""
        records = super().create(vals_list)
        for record in records:
            record._compute_totals()
        return records
    
    @api.depends('currency_id')
    def _compute_totals(self):
        """Dashboard toplamlarını hesapla"""
        for record in self:
            company = self.env.company
            
            # Kasa - account.journal'dan bakiye hesapla
            cash_journals = self.env['account.journal'].search([
                ('company_id', '=', company.id),
                ('type', '=', 'cash'),
            ])
            total_cash = 0.0
            for journal in cash_journals:
                if journal.default_account_id:
                    # Account move lines'dan bakiye hesapla
                    lines = self.env['account.move.line'].search([
                        ('account_id', '=', journal.default_account_id.id),
                        ('parent_state', '=', 'posted'),
                    ])
                    total_cash += sum(line.debit - line.credit for line in lines)
            
            # Banka
            bank_journals = self.env['account.journal'].search([
                ('company_id', '=', company.id),
                ('type', '=', 'bank'),
            ])
            total_bank = 0.0
            for journal in bank_journals:
                if journal.default_account_id:
                    lines = self.env['account.move.line'].search([
                        ('account_id', '=', journal.default_account_id.id),
                        ('parent_state', '=', 'posted'),
                    ])
                    total_bank += sum(line.debit - line.credit for line in lines)
            
            # Alacaklar
            partners = self.env['res.partner'].search([
                '|', ('company_id', '=', company.id), ('company_id', '=', False),
                ('customer_rank', '>', 0),
            ])
            total_receivable = sum(p.credit or 0.0 for p in partners)
            
            # Borçlar
            partners = self.env['res.partner'].search([
                '|', ('company_id', '=', company.id), ('company_id', '=', False),
                ('supplier_rank', '>', 0),
            ])
            total_payable = sum(p.debit or 0.0 for p in partners)
            
            record.total_cash = total_cash
            record.total_bank = total_bank
            record.total_receivable = total_receivable
            record.total_payable = total_payable
    
    def action_refresh_dashboard(self):
        """Dashboard'u yenile"""
        self._compute_totals()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Başarılı',
                'message': 'Dashboard güncellendi',
                'type': 'success',
                'sticky': False,
            }
        }
    
    @api.model
    def get_dashboard_data(self):
        """Dashboard verilerini getir (API için)"""
        dashboard = self.create({})
        dashboard._compute_totals()
        return {
            'total_cash': dashboard.total_cash,
            'total_bank': dashboard.total_bank,
            'total_receivable': dashboard.total_receivable,
            'total_payable': dashboard.total_payable,
        }
    
    @api.model
    def action_open_dashboard(self):
        """Dashboard'u aç - otomatik record oluştur"""
        dashboard = self.create({})
        dashboard._compute_totals()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Gösterge Paneli',
            'res_model': 'mobilsoft.dashboard',
            'view_mode': 'form',
            'res_id': dashboard.id,
            'target': 'current',
            'context': {'create': False, 'edit': False},
        }
