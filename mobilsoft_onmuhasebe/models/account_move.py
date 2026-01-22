# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class AccountMove(models.Model):
    """
    Faturalar - Türkiye'ye özel alanlar ve iyileştirmeler
    """
    _inherit = 'account.move'
    
    # Türkiye'ye özel alanlar (eğer yoksa)
    # Not: Odoo 19'da zaten KDV desteği var, sadece görünümü iyileştireceğiz
    
    def _get_turkish_tax_rates(self):
        """Türkiye KDV oranları"""
        return {
            '0': 0.0,
            '1': 1.0,
            '10': 10.0,
            '20': 20.0,
        }
