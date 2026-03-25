# -*- coding: utf-8 -*-
"""
MobilSoft Portal — Ana Controller
Login, logout, register, şirket seçimi
"""
import logging
import werkzeug

from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessDenied

_logger = logging.getLogger(__name__)


class MobilSoftPortalMain(http.Controller):

    # ==================== LOGIN ====================

    @http.route('/mobilsoft/login', type='http', auth='public', website=True, sitemap=False)
    def login_page(self, redirect=None, **kwargs):
        """Özel login sayfası."""
        if request.session.uid:
            return request.redirect(redirect or '/mobilsoft/')

        values = {
            'error': kwargs.get('error', ''),
            'login': kwargs.get('login', ''),
            'redirect': redirect or '/mobilsoft/',
        }
        return request.render('mobilsoft_portal.login_page', values)

    @http.route('/mobilsoft/login/submit', type='http', auth='public', methods=['POST'], csrf=True, website=True, sitemap=False)
    def login_submit(self, login, password, redirect='/mobilsoft/', **kwargs):
        """Login form submit."""
        try:
            credential = {'login': login, 'password': password, 'type': 'password'}
            auth_info = request.session.authenticate(request.env, credential)
            uid = auth_info.get('uid')
            if uid:
                _logger.info('MobilSoft Portal: Login başarılı: %s (uid=%s)', login, uid)
                return request.redirect(redirect)
        except AccessDenied:
            _logger.warning('MobilSoft Portal: AccessDenied for %s', login)
        except Exception as e:
            _logger.warning('MobilSoft Portal login hatası: %s', e, exc_info=True)

        return request.redirect(
            '/mobilsoft/login?error=1&login=%s' % werkzeug.utils.escape(login)
        )

    # ==================== REGISTER ====================

    @http.route('/mobilsoft/register', type='http', auth='public', website=True, sitemap=False)
    def register_page(self, **kwargs):
        """Kayıt sayfası (GET)."""
        if request.session.uid:
            return request.redirect('/mobilsoft/')

        values = {
            'error': kwargs.get('error', ''),
            'success': kwargs.get('success', ''),
            'form_data': {},
        }
        return request.render('mobilsoft_portal.register_page', values)

    @http.route('/mobilsoft/register/submit', type='http', auth='public', methods=['POST'], csrf=True, website=True, sitemap=False)
    def register_submit(self, **kwargs):
        """Kayıt form submit — mobilsoft_saas register mantığını çağırır."""
        env = request.env

        company_name = kwargs.get('company_name', '').strip()
        user_name = kwargs.get('user_name', '').strip()
        email = kwargs.get('email', '').strip().lower()
        password = kwargs.get('password', '')
        vat = kwargs.get('vat', '').strip()
        phone = kwargs.get('phone', '').strip()

        form_data = {
            'company_name': company_name,
            'user_name': user_name,
            'email': email,
            'vat': vat,
            'phone': phone,
        }

        # Validasyon
        if not company_name or not email or not password or not user_name:
            return request.render('mobilsoft_portal.register_page', {
                'error': 'Zorunlu alanlar eksik. Lütfen tüm zorunlu alanları doldurun.',
                'form_data': form_data,
            })

        if len(password) < 8:
            return request.render('mobilsoft_portal.register_page', {
                'error': 'Şifre en az 8 karakter olmalıdır.',
                'form_data': form_data,
            })

        # E-posta müsait mi?
        existing = env['res.users'].sudo().search([('login', '=', email)], limit=1)
        if existing:
            return request.render('mobilsoft_portal.register_page', {
                'error': 'Bu e-posta adresi zaten kullanımda.',
                'form_data': form_data,
            })

        # Şirket adı müsait mi?
        existing_company = env['res.company'].sudo().search([('name', '=ilike', company_name)], limit=1)
        if existing_company:
            return request.render('mobilsoft_portal.register_page', {
                'error': 'Bu şirket adı zaten kullanımda.',
                'form_data': form_data,
            })

        try:
            # 1. Şirket oluştur
            tr_country = env['res.country'].sudo().search([('code', '=', 'TR')], limit=1)
            try_currency = env['res.currency'].sudo().search([('name', '=', 'TRY')], limit=1)

            company_vals = {
                'name': company_name,
                'country_id': tr_country.id if tr_country else False,
                'currency_id': try_currency.id if try_currency else False,
            }
            if vat:
                company_vals['vat'] = vat
            if phone:
                company_vals['phone'] = phone
            if email:
                company_vals['email'] = email

            company = env['res.company'].sudo().create(company_vals)
            _logger.info('MobilSoft Portal: Şirket oluşturuldu: %s (ID: %s)', company.name, company.id)

            # 2. Hesap planı yükle
            try:
                env['account.chart.template'].sudo().try_loading('tr', company, install_demo=False)
                _logger.info('MobilSoft Portal: Türk hesap planı yüklendi.')
            except Exception as e:
                _logger.warning('MobilSoft Portal: Hesap planı yüklenemedi: %s', e)

            # 3. Kullanıcı oluştur
            user = env['res.users'].sudo().create({
                'name': user_name,
                'login': email,
                'password': password,
                'company_id': company.id,
                'company_ids': [(6, 0, [company.id])],
            })
            _logger.info('MobilSoft Portal: Kullanıcı oluşturuldu: %s (ID: %s)', user.login, user.id)

            # 4. Grup atamaları
            group_xml_ids = [
                'base.group_user',
                'base.group_partner_manager',
                'account.group_account_invoice',
                'account.group_account_basic',
                'product.group_product_manager',
                'product.group_product_variant',
                'sales_team.group_sale_salesman',
                'stock.group_stock_user',
                'point_of_sale.group_pos_user',
                'point_of_sale.group_pos_manager',
            ]
            groups_to_add = []
            for ref in group_xml_ids:
                g = env.ref(ref, raise_if_not_found=False)
                if g:
                    groups_to_add.append(g.id)
            if groups_to_add:
                try:
                    user.sudo().write({'group_ids': [(6, 0, groups_to_add)]})
                except Exception as ge:
                    _logger.warning('MobilSoft Portal: Grup ataması başarısız: %s', ge)

            # 5. Temel günlükler
            cash_journal = env['account.journal'].sudo().search([
                ('company_id', '=', company.id), ('type', '=', 'cash')
            ], limit=1)
            if not cash_journal:
                cash_account = env['account.account'].sudo().search([
                    ('company_ids', 'in', [company.id]), ('code', 'like', '100')
                ], limit=1)
                cash_journal = env['account.journal'].sudo().create({
                    'name': 'Kasa', 'type': 'cash', 'code': 'CSH1',
                    'company_id': company.id,
                    'default_account_id': cash_account.id if cash_account else False,
                })
                env['account.journal'].sudo().create({
                    'name': 'Satışlar', 'type': 'sale', 'code': 'SFAT',
                    'company_id': company.id,
                })
                env['account.journal'].sudo().create({
                    'name': 'Satınalma', 'type': 'purchase', 'code': 'AFAT',
                    'company_id': company.id,
                })

            # 6. POS konfigürasyonu
            try:
                existing_pos = env['pos.config'].sudo().search([('company_id', '=', company.id)], limit=1)
                if not existing_pos:
                    cash_pm = env['pos.payment.method'].sudo().search([
                        ('company_id', '=', company.id)
                    ], limit=1)
                    if not cash_pm:
                        pm_vals = {
                            'name': 'Nakit', 'payment_method_type': 'cash',
                            'company_id': company.id, 'is_cash_count': True,
                        }
                        if cash_journal:
                            pm_vals['journal_id'] = cash_journal.id
                        cash_pm = env['pos.payment.method'].sudo().create(pm_vals)

                    sale_journal = env['account.journal'].sudo().search([
                        ('company_id', '=', company.id), ('type', '=', 'sale')
                    ], limit=1)
                    pos_vals = {
                        'name': f"{company.name} Kasası",
                        'company_id': company.id,
                        'payment_method_ids': [(6, 0, [cash_pm.id])],
                    }
                    if sale_journal:
                        pos_vals['journal_id'] = sale_journal.id
                        pos_vals['invoice_journal_id'] = sale_journal.id
                    env['pos.config'].sudo().create(pos_vals)
            except Exception as pe:
                _logger.warning('MobilSoft Portal: POS konfigürasyonu oluşturulamadı: %s', pe)

            # 7. Home action ayarla
            try:
                ms_home_action = env.ref('mobilsoft_interface.action_mobilsoft_app', raise_if_not_found=False)
                if ms_home_action:
                    user.sudo().write({'action_id': ms_home_action.id})
            except Exception:
                pass

            # 8. Otomatik login
            try:
                credential = {'login': email, 'password': password, 'type': 'password'}
                request.session.authenticate(request.env, credential)
                _logger.info('MobilSoft Portal: Otomatik login başarılı: %s', email)
                return request.redirect('/mobilsoft/dashboard')
            except Exception as le:
                _logger.warning('MobilSoft Portal: Otomatik login başarısız: %s', le)
                return request.redirect('/mobilsoft/login?login=%s' % werkzeug.utils.escape(email))

        except Exception as e:
            _logger.error('MobilSoft Portal kayıt hatası: %s', e, exc_info=True)
            try:
                request.env.cr.rollback()
            except Exception:
                pass
            return request.render('mobilsoft_portal.register_page', {
                'error': f'Kayıt sırasında bir hata oluştu: {str(e)}',
                'form_data': form_data,
            })

    # ==================== LOGOUT ====================

    @http.route('/mobilsoft/logout', type='http', auth='user', sitemap=False)
    def logout(self, **kwargs):
        """Logout ve login sayfasına yönlendir."""
        request.session.logout()
        return request.redirect('/mobilsoft/login')

    @http.route('/mobilsoft/', type='http', auth='user', website=True, sitemap=False)
    def portal_home(self, **kwargs):
        """Ana sayfa — dashboard'a yönlendir."""
        return request.redirect('/mobilsoft/dashboard')

