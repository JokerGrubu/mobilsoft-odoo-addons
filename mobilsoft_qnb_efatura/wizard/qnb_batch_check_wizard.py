# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class QNBBatchCheckWizard(models.TransientModel):
    _name = 'qnb.batch.check.wizard'
    _description = 'QNB Toplu e-Fatura Mükellefi Kontrolü'

    partner_ids = fields.Many2many(
        'res.partner',
        string='Müşteriler',
        domain=[('is_company', '=', True), ('vat', '!=', False)]
    )
    result_text = fields.Html(string='Sonuç', readonly=True)

    def action_check(self):
        """Seçili müşterileri kontrol et"""
        self.ensure_one()
        
        if not self.partner_ids:
            raise UserError(_('Lütfen en az bir müşteri seçin.'))
        
        return self._check_partners(self.partner_ids)

    def action_check_all(self):
        """Tüm şirket müşterilerini kontrol et"""
        self.ensure_one()
        
        partners = self.env['res.partner'].search([
            ('is_company', '=', True),
            ('vat', '!=', False),
            ('vat', '!=', ''),
        ])
        
        if not partners:
            raise UserError(_('VKN/TCKN bilgisi olan müşteri bulunamadı.'))
        
        return self._check_partners(partners)

    def _check_partners(self, partners):
        """Müşterileri kontrol et ve sonucu göster"""
        from ..models.qnb_api import QNBeSolutionsAPI
        
        company = self.env.company
        api = QNBeSolutionsAPI(company)
        
        results = {
            'registered': [],
            'not_registered': [],
            'error': []
        }
        
        for partner in partners:
            try:
                vkn = partner.vat.replace('TR', '').replace(' ', '')
                result = api.check_registered_user(vkn)
                
                if result.get('is_registered'):
                    partner.write({
                        'is_efatura_registered': True,
                        'efatura_alias': result.get('alias', ''),
                        'efatura_alias_type': result.get('alias_type', ''),
                        'efatura_check_date': fields.Datetime.now(),
                    })
                    results['registered'].append({
                        'name': partner.name,
                        'vkn': vkn,
                        'alias': result.get('alias', '')
                    })
                else:
                    partner.write({
                        'is_efatura_registered': False,
                        'efatura_alias': False,
                        'efatura_alias_type': False,
                        'efatura_check_date': fields.Datetime.now(),
                    })
                    results['not_registered'].append({
                        'name': partner.name,
                        'vkn': vkn
                    })
            except Exception as e:
                results['error'].append({
                    'name': partner.name,
                    'vkn': partner.vat,
                    'error': str(e)
                })
                _logger.error(f"Partner check error for {partner.name}: {e}")
        
        # Sonuç HTML'i oluştur
        html = self._generate_result_html(results)
        self.result_text = html
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'qnb.batch.check.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _generate_result_html(self, results):
        """Sonuç HTML'i oluştur"""
        html = '<div class="container">'
        
        # Özet
        total = len(results['registered']) + len(results['not_registered']) + len(results['error'])
        html += f'''
        <div class="row mb-3">
            <div class="col-12">
                <h4>Kontrol Sonucu</h4>
                <p>Toplam <strong>{total}</strong> müşteri kontrol edildi.</p>
            </div>
        </div>
        '''
        
        # Kayıtlı olanlar
        if results['registered']:
            html += '''
            <div class="alert alert-success">
                <h5><i class="fa fa-check-circle"></i> e-Fatura Mükellefleri ({count})</h5>
                <ul class="mb-0">
            '''.format(count=len(results['registered']))
            for r in results['registered']:
                html += f'<li><strong>{r["name"]}</strong> ({r["vkn"]}) - Alias: {r["alias"]}</li>'
            html += '</ul></div>'
        
        # Kayıtlı olmayanlar
        if results['not_registered']:
            html += '''
            <div class="alert alert-warning">
                <h5><i class="fa fa-exclamation-triangle"></i> e-Fatura Mükellefi Olmayan ({count})</h5>
                <ul class="mb-0">
            '''.format(count=len(results['not_registered']))
            for r in results['not_registered']:
                html += f'<li><strong>{r["name"]}</strong> ({r["vkn"]})</li>'
            html += '</ul></div>'
        
        # Hatalar
        if results['error']:
            html += '''
            <div class="alert alert-danger">
                <h5><i class="fa fa-times-circle"></i> Hata Oluşan ({count})</h5>
                <ul class="mb-0">
            '''.format(count=len(results['error']))
            for r in results['error']:
                html += f'<li><strong>{r["name"]}</strong> ({r["vkn"]}) - Hata: {r["error"]}</li>'
            html += '</ul></div>'
        
        html += '</div>'
        return html
