# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import re


class ResPartner(models.Model):
    """
    Cari Hesaplar (Müşteri/Tedarikçi) - Türkiye'ye özel alanlar
    """
    _inherit = 'res.partner'

    # Türkiye'ye özel alanlar
    vkn = fields.Char(
        string='VKN',
        size=10,
        help='Vergi Kimlik Numarası (10 haneli)',
        index=True,
    )
    
    tckn = fields.Char(
        string='TCKN',
        size=11,
        help='T.C. Kimlik Numarası (11 haneli)',
        index=True,
    )
    
    # VKN/TCKN otomatik belirleme
    @api.onchange('is_company', 'vat')
    def _onchange_vat(self):
        """VAT alanından VKN/TCKN otomatik ayır"""
        if self.vat:
            # Sadece rakamları al
            vat_clean = re.sub(r'\D', '', self.vat)
            if len(vat_clean) == 10:
                self.vkn = vat_clean
                self.tckn = False
            elif len(vat_clean) == 11:
                self.tckn = vat_clean
                self.vkn = False
    
    iban = fields.Char(
        string='IBAN',
        size=34,
        help='IBAN numarası (TR ile başlamalı)',
    )
    
    is_efatura_user = fields.Boolean(
        string='e-Fatura Kullanıcısı',
        default=False,
        help='GİB e-Fatura sistemine kayıtlı mı?',
    )
    
    efatura_alias = fields.Char(
        string='e-Fatura Alias',
        help='GİB e-Fatura sistemindeki alias (e-posta)',
    )
    
    # Durum badge'leri
    partner_status = fields.Selection(
        [
            ('active', 'Aktif'),
            ('passive', 'Pasif'),
            ('blocked', 'Bloke'),
        ],
        string='Durum',
        default='active',
        required=True,
    )
    
    # Computed fields
    total_receivable = fields.Monetary(
        string='Toplam Alacak',
        compute='_compute_balances',
        currency_field='currency_id',
        store=True,
    )
    
    total_payable = fields.Monetary(
        string='Toplam Borç',
        compute='_compute_balances',
        currency_field='currency_id',
        store=True,
    )
    
    net_balance = fields.Monetary(
        string='Net Bakiye',
        compute='_compute_balances',
        currency_field='currency_id',
        store=True,
    )
    
    @api.depends('credit', 'debit')
    def _compute_balances(self):
        """Cari bakiye hesapla"""
        for partner in self:
            partner.total_receivable = partner.credit or 0.0
            partner.total_payable = partner.debit or 0.0
            partner.net_balance = partner.credit - partner.debit
    
    # Validations
    @api.constrains('vkn')
    def _check_vkn(self):
        """VKN doğrulama (10 haneli, sadece rakam)"""
        for partner in self:
            if partner.vkn:
                if not partner.vkn.isdigit() or len(partner.vkn) != 10:
                    raise ValidationError(_('VKN 10 haneli rakam olmalıdır!'))
    
    @api.constrains('tckn')
    def _check_tckn(self):
        """TCKN doğrulama (11 haneli, sadece rakam)"""
        for partner in self:
            if partner.tckn:
                if not partner.tckn.isdigit() or len(partner.tckn) != 11:
                    raise ValidationError(_('TCKN 11 haneli rakam olmalıdır!'))
    
    @api.constrains('iban')
    def _check_iban(self):
        """IBAN doğrulama (TR ile başlamalı, 26-34 karakter)"""
        for partner in self:
            if partner.iban:
                iban_clean = partner.iban.replace(' ', '').upper()
                if not iban_clean.startswith('TR') or len(iban_clean) < 26 or len(iban_clean) > 34:
                    raise ValidationError(_('IBAN TR ile başlamalı ve 26-34 karakter olmalıdır!'))
                self.iban = iban_clean
