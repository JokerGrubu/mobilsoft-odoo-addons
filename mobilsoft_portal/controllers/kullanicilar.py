# -*- coding: utf-8 -*-
"""
MobilSoft Portal — Kullanıcı & Rol Yönetimi Controller
Roller ir.config_parameter içinde JSON olarak saklanır (Odoo 19 uyumlu).
"""
import json
import logging

from odoo import http
from odoo.http import request
from .helpers import get_company_ids, get_default_company_id, check_record_access

_logger = logging.getLogger(__name__)

ROLES_PARAM_KEY = 'mobilsoft_portal_roles'

PERMISSION_MODULES = [
    ('cariler', 'Cariler'),
    ('urunler', 'Ürünler'),
    ('faturalar', 'Faturalar'),
    ('siparisler', 'Siparişler'),
    ('odemeler', 'Ödemeler'),
    ('raporlar', 'Raporlar'),
    ('ayarlar', 'Ayarlar'),
]

PERMISSION_LEVELS = {
    'cariler': ['view', 'edit'],
    'urunler': ['view', 'edit'],
    'faturalar': ['view', 'create'],
    'siparisler': ['view', 'create'],
    'odemeler': ['view', 'create'],
    'raporlar': ['view'],
    'ayarlar': ['access'],
}


class MobilSoftKullanicilar(http.Controller):

    # ---- Role helpers (JSON in ir.config_parameter) ----

    def _load_roles(self):
        """Load all roles from ir.config_parameter. Returns dict {id: {name, perms}}."""
        raw = request.env['ir.config_parameter'].sudo().get_param(ROLES_PARAM_KEY, '{}')
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def _save_roles(self, roles_dict):
        """Save roles dict to ir.config_parameter."""
        request.env['ir.config_parameter'].sudo().set_param(ROLES_PARAM_KEY, json.dumps(roles_dict, ensure_ascii=False))

    def _get_user_role_id(self, user_rec):
        """Get role_id stored in ir.config_parameter for a user."""
        key = f'mobilsoft_user_role_{user_rec.id}'
        val = request.env['ir.config_parameter'].sudo().get_param(key, '')
        return val if val else ''

    def _set_user_role_id(self, user_id, role_id):
        """Set role_id for a user."""
        key = f'mobilsoft_user_role_{user_id}'
        request.env['ir.config_parameter'].sudo().set_param(key, str(role_id))

    def _next_role_id(self, roles_dict):
        """Generate next role ID."""
        if not roles_dict:
            return '1'
        return str(max(int(k) for k in roles_dict.keys()) + 1)

    # ==================== KULLANICILAR ====================

    @http.route('/mobilsoft/ayarlar/kullanicilar', type='http', auth='user', website=True, sitemap=False)
    def kullanici_list(self, **kwargs):
        try:
            company_ids = get_company_ids()
            users = request.env['res.users'].sudo().search([
                ('company_id', 'in', company_ids),
                ('share', '=', False),
            ], order='name asc')
            roles = self._load_roles()
            return request.render('mobilsoft_portal.kullanicilar_list', {
                'users': users,
                'roles': roles,
                'success': kwargs.get('success', ''),
                'error': kwargs.get('error', ''),
            })
        except Exception as e:
            _logger.exception("Kullanıcı listesi hatası")
            return request.render('mobilsoft_portal.kullanicilar_list', {
                'users': request.env['res.users'].sudo().browse([]),
                'roles': {},
                'error': str(e),
                'success': '',
            })

    @http.route('/mobilsoft/ayarlar/kullanicilar/yeni', type='http', auth='user', website=True, sitemap=False)
    def kullanici_form_new(self, **kwargs):
        try:
            roles = self._load_roles()
            return request.render('mobilsoft_portal.kullanici_form', {
                'user_rec': None,
                'roles': roles,
                'user_role_id': '',
                'is_new': True,
                'error': kwargs.get('error', ''),
            })
        except Exception as e:
            _logger.exception("Yeni kullanıcı formu hatası")
            return request.redirect(f'/mobilsoft/ayarlar/kullanicilar?error={e}')

    @http.route('/mobilsoft/ayarlar/kullanicilar/<int:user_id>/duzenle', type='http', auth='user', website=True, sitemap=False)
    def kullanici_form_edit(self, user_id, **kwargs):
        try:
            user_rec = request.env['res.users'].sudo().browse(user_id)
            if not user_rec.exists():
                return request.redirect('/mobilsoft/ayarlar/kullanicilar?error=Kullanıcı+bulunamadı')
            roles = self._load_roles()
            user_role_id = self._get_user_role_id(user_rec)
            return request.render('mobilsoft_portal.kullanici_form', {
                'user_rec': user_rec,
                'roles': roles,
                'user_role_id': user_role_id,
                'is_new': False,
                'error': kwargs.get('error', ''),
            })
        except Exception as e:
            _logger.exception("Kullanıcı düzenle hatası")
            return request.redirect(f'/mobilsoft/ayarlar/kullanicilar?error={e}')

    @http.route('/mobilsoft/ayarlar/kullanicilar/kaydet', type='http', auth='user', website=True, methods=['POST'], sitemap=False, csrf=True)
    def kullanici_save(self, **post):
        try:
            user_id = int(post.get('user_id', 0))
            name = post.get('name', '').strip()
            login = post.get('login', '').strip()
            phone = post.get('phone', '').strip()
            password = post.get('password', '').strip()
            role_id = post.get('role_id', '').strip()
            active = post.get('active') == 'on'

            if not name or not login:
                return request.redirect('/mobilsoft/ayarlar/kullanicilar?error=Ad+ve+e-posta+zorunlu')

            company = request.env.company
            vals = {
                'name': name,
                'login': login,
                'phone': phone,
                'active': active,
                'company_id': company.id,
                'company_ids': [(4, company.id)],
            }

            if user_id:
                user_rec = request.env['res.users'].sudo().browse(user_id)
                if password:
                    vals['password'] = password
                user_rec.write(vals)
            else:
                if not password:
                    return request.redirect('/mobilsoft/ayarlar/kullanicilar/yeni?error=Şifre+zorunlu')
                vals['password'] = password
                user_rec = request.env['res.users'].sudo().create(vals)
                user_id = user_rec.id

            # Save role assignment
            if role_id:
                self._set_user_role_id(user_id, role_id)

            return request.redirect('/mobilsoft/ayarlar/kullanicilar?success=Kaydedildi')
        except Exception as e:
            _logger.exception("Kullanıcı kaydetme hatası")
            return request.redirect(f'/mobilsoft/ayarlar/kullanicilar?error={e}')

    @http.route('/mobilsoft/ayarlar/kullanicilar/<int:user_id>/sil', type='http', auth='user', website=True, methods=['POST'], sitemap=False, csrf=True)
    def kullanici_deactivate(self, user_id, **post):
        try:
            user_rec = request.env['res.users'].sudo().browse(user_id)
            if user_rec.exists():
                user_rec.write({'active': False})
            return request.redirect('/mobilsoft/ayarlar/kullanicilar?success=Kullanıcı+devre+dışı+bırakıldı')
        except Exception as e:
            _logger.exception("Kullanıcı devre dışı bırakma hatası")
            return request.redirect(f'/mobilsoft/ayarlar/kullanicilar?error={e}')

    @http.route('/mobilsoft/ayarlar/kullanicilar/<int:user_id>/sifre-sifirla', type='http', auth='user', website=True, methods=['POST'], sitemap=False, csrf=True)
    def kullanici_reset_password(self, user_id, **post):
        try:
            user_rec = request.env['res.users'].sudo().browse(user_id)
            if user_rec.exists():
                new_pass = post.get('new_password', '').strip()
                if new_pass:
                    user_rec.write({'password': new_pass})
                    return request.redirect('/mobilsoft/ayarlar/kullanicilar?success=Şifre+sıfırlandı')
                else:
                    return request.redirect(f'/mobilsoft/ayarlar/kullanicilar/{user_id}/duzenle?error=Şifre+boş+olamaz')
            return request.redirect('/mobilsoft/ayarlar/kullanicilar?error=Kullanıcı+bulunamadı')
        except Exception as e:
            _logger.exception("Şifre sıfırlama hatası")
            return request.redirect(f'/mobilsoft/ayarlar/kullanicilar?error={e}')

    # ==================== ROLLER ====================

    @http.route('/mobilsoft/ayarlar/roller', type='http', auth='user', website=True, sitemap=False)
    def rol_list(self, **kwargs):
        try:
            roles = self._load_roles()
            role_data = []
            for rid, rdata in roles.items():
                role_data.append({
                    'id': rid,
                    'name': rdata.get('name', ''),
                    'perms': rdata.get('perms', {}),
                })
            return request.render('mobilsoft_portal.roller_list', {
                'role_data': role_data,
                'success': kwargs.get('success', ''),
                'error': kwargs.get('error', ''),
            })
        except Exception as e:
            _logger.exception("Rol listesi hatası")
            return request.render('mobilsoft_portal.roller_list', {
                'role_data': [],
                'error': str(e),
                'success': '',
            })

    @http.route('/mobilsoft/ayarlar/roller/yeni', type='http', auth='user', website=True, sitemap=False)
    def rol_form_new(self, **kwargs):
        try:
            return request.render('mobilsoft_portal.rol_form', {
                'role': None,
                'role_id': '',
                'perms': {},
                'is_new': True,
                'modules': PERMISSION_MODULES,
                'levels': PERMISSION_LEVELS,
                'error': kwargs.get('error', ''),
            })
        except Exception as e:
            _logger.exception("Yeni rol formu hatası")
            return request.redirect(f'/mobilsoft/ayarlar/roller?error={e}')

    @http.route('/mobilsoft/ayarlar/roller/<string:role_id>/duzenle', type='http', auth='user', website=True, sitemap=False)
    def rol_form_edit(self, role_id, **kwargs):
        try:
            roles = self._load_roles()
            rdata = roles.get(str(role_id))
            if not rdata:
                return request.redirect('/mobilsoft/ayarlar/roller?error=Rol+bulunamadı')
            return request.render('mobilsoft_portal.rol_form', {
                'role': rdata,
                'role_id': str(role_id),
                'perms': rdata.get('perms', {}),
                'is_new': False,
                'modules': PERMISSION_MODULES,
                'levels': PERMISSION_LEVELS,
                'error': kwargs.get('error', ''),
            })
        except Exception as e:
            _logger.exception("Rol düzenle hatası")
            return request.redirect(f'/mobilsoft/ayarlar/roller?error={e}')

    @http.route('/mobilsoft/ayarlar/roller/kaydet', type='http', auth='user', website=True, methods=['POST'], sitemap=False, csrf=True)
    def rol_save(self, **post):
        try:
            role_id = post.get('role_id', '').strip()
            name = post.get('name', '').strip()

            if not name:
                return request.redirect('/mobilsoft/ayarlar/roller?error=Rol+adı+zorunlu')

            roles = self._load_roles()

            # Build permissions dict from form
            perms = {}
            for mod_key, _label in PERMISSION_MODULES:
                val = post.get(f'perm_{mod_key}', 'none')
                if val != 'none':
                    perms[mod_key] = val

            if role_id and role_id in roles:
                roles[role_id]['name'] = name
                roles[role_id]['perms'] = perms
            else:
                new_id = self._next_role_id(roles)
                roles[new_id] = {'name': name, 'perms': perms}

            self._save_roles(roles)
            return request.redirect('/mobilsoft/ayarlar/roller?success=Kaydedildi')
        except Exception as e:
            _logger.exception("Rol kaydetme hatası")
            return request.redirect(f'/mobilsoft/ayarlar/roller?error={e}')
