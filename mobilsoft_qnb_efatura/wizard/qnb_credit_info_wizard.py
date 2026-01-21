# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class QNBCreditInfoWizard(models.TransientModel):
    _name = 'qnb.credit.info.wizard'
    _description = 'QNB Kontör Bilgisi'

    efatura_credit = fields.Integer(string='e-Fatura Kontör', readonly=True)
    efatura_used = fields.Integer(string='e-Fatura Kullanılan', readonly=True)
    earsiv_credit = fields.Integer(string='e-Arşiv Kontör', readonly=True)
    earsiv_used = fields.Integer(string='e-Arşiv Kullanılan', readonly=True)
    eirsaliye_credit = fields.Integer(string='e-İrsaliye Kontör', readonly=True)
    eirsaliye_used = fields.Integer(string='e-İrsaliye Kullanılan', readonly=True)
    last_check_date = fields.Datetime(string='Son Kontrol', readonly=True)

    @api.model
    def default_get(self, fields_list):
        """Açılışta kontör bilgilerini çek"""
        res = super().default_get(fields_list)
        
        try:
            credit_info = self._get_credit_info()
            res.update(credit_info)
        except Exception as e:
            _logger.warning(f"Could not fetch credit info: {e}")
        
        return res

    def _get_credit_info(self):
        """API'den kontör bilgilerini çek"""
        from ..models.qnb_api import QNBeSolutionsAPI
        
        company = self.env.company
        api = QNBeSolutionsAPI(company)
        
        result = api.get_credit_status()
        
        return {
            'efatura_credit': result.get('efatura_credit', 0),
            'efatura_used': result.get('efatura_used', 0),
            'earsiv_credit': result.get('earsiv_credit', 0),
            'earsiv_used': result.get('earsiv_used', 0),
            'eirsaliye_credit': result.get('eirsaliye_credit', 0),
            'eirsaliye_used': result.get('eirsaliye_used', 0),
            'last_check_date': fields.Datetime.now(),
        }

    def action_refresh(self):
        """Kontör bilgilerini yenile"""
        self.ensure_one()
        
        try:
            credit_info = self._get_credit_info()
            self.write(credit_info)
        except Exception as e:
            raise UserError(_('Kontör bilgisi alınamadı: %s') % str(e))
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'qnb.credit.info.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
