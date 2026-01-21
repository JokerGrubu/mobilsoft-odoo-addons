# -*- coding: utf-8 -*-

from odoo import http
from odoo.addons.website.controllers import main as website_main
from odoo.http import request


class Website(website_main.Website):
    
    def _login_redirect(self, uid, redirect=None):
        """ Login sonrası /web route'una yönlendir (database session'da zaten var) """
        if not redirect and request.params.get('login_success'):
            if request.env['res.users'].browse(uid)._is_internal():
                # Database session'da zaten var, sadece /web'e yönlendir
                redirect = '/web'
            else:
                redirect = '/my'
        return super()._login_redirect(uid, redirect=redirect)
