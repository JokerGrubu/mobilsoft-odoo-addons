# -*- coding: utf-8 -*-
"""
MobilSoft Interface - Kullanıcı Ana Sayfa Yönetimi

MobilSoft kiracı kullanıcıları giriş yaptığında standart Odoo yerine
MobilSoft özel dashboard'una yönlendirilir.
"""

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    is_mobilsoft_tenant = fields.Boolean(
        string='MobilSoft Kiracı',
        default=False,
        help='Bu kullanıcı bir MobilSoft kiracısıdır. Özel arayüz gösterilir.'
    )

    def _get_mobilsoft_home_action(self):
        """MobilSoft ana sayfa action'ını döndür"""
        action = self.env.ref(
            'mobilsoft_interface.action_mobilsoft_home',
            raise_if_not_found=False
        )
        return action

    @api.model
    def _default_locale(self):
        """Odoo 19 uyumu"""
        return super()._default_locale()
