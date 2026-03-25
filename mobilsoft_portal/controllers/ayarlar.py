# -*- coding: utf-8 -*-
"""
MobilSoft Portal — Ayarlar Controller
Şirket bilgileri, kullanıcı profil, şifre değiştirme
"""
import logging
import base64

from odoo import http
from odoo.http import request
from .helpers import get_company_ids, get_default_company_id, check_record_access

_logger = logging.getLogger(__name__)


class MobilSoftAyarlar(http.Controller):

    @http.route('/mobilsoft/ayarlar', type='http', auth='user', website=True, sitemap=False)
    def ayarlar_index(self, **kwargs):
        """Ayarlar ana sayfası."""
        env = request.env
        values = {
            'page_name': 'ayarlar',
            'company': env.company,
            'user': env.user,
            'success': kwargs.get('success', ''),
            'error': kwargs.get('error', ''),
        }
        return request.render('mobilsoft_portal.ayarlar_index', values)

    # ==================== ŞİRKET BİLGİLERİ ====================

    @http.route('/mobilsoft/ayarlar/sirket', type='http', auth='user', website=True, sitemap=False)
    def sirket_form(self, **kwargs):
        env = request.env
        countries = env['res.country'].sudo().search([], order='name asc')
        states = []
        if env.company.country_id:
            states = env['res.country.state'].sudo().search([
                ('country_id', '=', env.company.country_id.id)
            ], order='name asc')

        values = {
            'page_name': 'ayarlar',
            'company': env.company,
            'countries': countries,
            'states': states,
            'error': kwargs.get('error', ''),
            'success': kwargs.get('success', ''),
        }
        return request.render('mobilsoft_portal.ayarlar_sirket', values)

    @http.route('/mobilsoft/ayarlar/sirket/kaydet', type='http', auth='user', methods=['POST'], csrf=True, website=True, sitemap=False)
    def sirket_save(self, **kwargs):
        env = request.env
        company = env.company.sudo()

        try:
            vals = {
                'name': kwargs.get('name', '').strip() or company.name,
                'vat': kwargs.get('vat', '').strip() or False,
                'phone': kwargs.get('phone', '').strip() or False,
                'email': kwargs.get('email', '').strip() or False,
                'website': kwargs.get('website_url', '').strip() or False,
                'street': kwargs.get('street', '').strip() or False,
                'city': kwargs.get('city', '').strip() or False,
                'zip': kwargs.get('zip', '').strip() or False,
            }
            country_id = int(kwargs.get('country_id', 0) or 0)
            state_id = int(kwargs.get('state_id', 0) or 0)
            if country_id:
                vals['country_id'] = country_id
            if state_id:
                vals['state_id'] = state_id

            logo = kwargs.get('logo')
            if logo and hasattr(logo, 'read'):
                data = logo.read()
                if data:
                    vals['logo'] = base64.b64encode(data)

            company.write(vals)
            return request.redirect('/mobilsoft/ayarlar/sirket?success=Şirket bilgileri güncellendi')
        except Exception as e:
            _logger.error('Şirket güncelleme hatası: %s', e)
            return request.redirect(f'/mobilsoft/ayarlar/sirket?error={str(e)[:200]}')

    # ==================== KULLANICI PROFİL ====================

    @http.route('/mobilsoft/ayarlar/profil', type='http', auth='user', website=True, sitemap=False)
    def profil_form(self, **kwargs):
        values = {
            'page_name': 'ayarlar',
            'user': request.env.user,
            'error': kwargs.get('error', ''),
            'success': kwargs.get('success', ''),
        }
        return request.render('mobilsoft_portal.ayarlar_profil', values)

    @http.route('/mobilsoft/ayarlar/profil/kaydet', type='http', auth='user', methods=['POST'], csrf=True, website=True, sitemap=False)
    def profil_save(self, **kwargs):
        user = request.env.user.sudo()

        try:
            vals = {
                'name': kwargs.get('name', '').strip() or user.name,
            }
            phone = kwargs.get('phone', '').strip()
            if phone:
                vals['phone'] = phone

            avatar = kwargs.get('avatar')
            if avatar and hasattr(avatar, 'read'):
                data = avatar.read()
                if data:
                    vals['image_1920'] = base64.b64encode(data)

            user.write(vals)
            return request.redirect('/mobilsoft/ayarlar/profil?success=Profil güncellendi')
        except Exception as e:
            return request.redirect(f'/mobilsoft/ayarlar/profil?error={str(e)[:200]}')

    # ==================== GELİŞMİŞ AYARLAR ====================

    @http.route('/mobilsoft/ayarlar/gelismis', type='http', auth='user', website=True, sitemap=False)
    def gelismis_ayarlar(self, **kwargs):
        """Gelişmiş ayarlar — döviz, vergi, ödeme yöntemleri vb."""
        env = request.env
        company = env.company.sudo()

        # Para birimleri
        currencies = env['res.currency'].sudo().search([('active', '=', True)], order='name asc')

        # Vergi tanımları (şirketin)
        taxes = env['account.tax'].sudo().search([
            ('company_id', '=', company.id),
        ], order='type_tax_use, sequence')

        # Ödeme yöntemleri (journal — bank/cash)
        journals = env['account.journal'].sudo().search([
            ('company_id', '=', company.id),
            ('type', 'in', ['bank', 'cash']),
        ], order='name asc')

        # Ürün kategorileri
        categories = env['product.category'].sudo().search([], order='complete_name asc')

        # Hesap planı (ilk 50)
        try:
            accounts = env['account.account'].sudo().search([
                ('company_ids', 'in', [company.id]),
            ], order='code asc', limit=50)
        except Exception:
            try:
                accounts = env['account.account'].sudo().search([
                    ('company_id', '=', company.id),
                ], order='code asc', limit=50)
            except Exception:
                accounts = env['account.account'].sudo().search([], order='code asc', limit=50)

        # Mali yıl / dönem bilgisi
        try:
            fiscal_year = env['account.fiscal.year'].sudo().search([
                ('company_id', '=', company.id),
            ], order='date_from desc', limit=5)
        except Exception:
            fiscal_year = []

        values = {
            'page_name': 'ayarlar',
            'company': company,
            'currencies': currencies,
            'company_currency': company.currency_id,
            'taxes': taxes,
            'journals': journals,
            'categories': categories,
            'accounts': accounts,
            'fiscal_years': fiscal_year,
            'error': kwargs.get('error', ''),
            'success': kwargs.get('success', ''),
        }
        return request.render('mobilsoft_portal.ayarlar_gelismis', values)

    @http.route('/mobilsoft/ayarlar/gelismis/kaydet', type='http', auth='user', methods=['POST'], csrf=True, website=True, sitemap=False)
    def gelismis_save(self, **kwargs):
        """Gelişmiş ayarları kaydet."""
        env = request.env
        company = env.company.sudo()

        try:
            # Para birimi değişikliği
            currency_id = int(kwargs.get('currency_id', 0) or 0)
            if currency_id and currency_id != company.currency_id.id:
                company.write({'currency_id': currency_id})

            return request.redirect('/mobilsoft/ayarlar/gelismis?success=Ayarlar güncellendi')
        except Exception as e:
            _logger.error('Gelişmiş ayar güncelleme hatası: %s', e)
            return request.redirect(f'/mobilsoft/ayarlar/gelismis?error={str(e)[:200]}')

    # ==================== ENTEGRASYONLAR ====================

    @http.route('/mobilsoft/ayarlar/entegrasyonlar', type='http', auth='user', website=True, sitemap=False)
    def entegrasyonlar(self, **kwargs):
        """Entegrasyonlar ana sayfası — banka, e-fatura, pazaryeri."""
        env = request.env

        # Banka connector'ları (model yoksa graceful fallback)
        bank_connectors = []
        try:
            if 'mobilsoft.bank.connector' in env:
                bank_connectors = env['mobilsoft.bank.connector'].sudo().search([
                    ('company_id', 'in', get_company_ids()),
                ])
        except Exception:
            pass

        values = {
            'page_name': 'ayarlar',
            'bank_connectors': bank_connectors,
            'error': kwargs.get('error', ''),
            'success': kwargs.get('success', ''),
        }
        return request.render('mobilsoft_portal.ayarlar_entegrasyonlar', values)

    @http.route('/mobilsoft/ayarlar/banka-entegrasyon', type='http', auth='user', website=True, sitemap=False)
    def banka_entegrasyon(self, **kwargs):
        """Banka entegrasyon listesi ve form."""
        env = request.env

        connectors = []
        edit_connector = None
        try:
            if 'mobilsoft.bank.connector' in env:
                connectors = env['mobilsoft.bank.connector'].sudo().search([
                    ('company_id', 'in', get_company_ids()),
                ], order='name asc')
                edit_id = int(kwargs.get('edit', 0) or 0)
                if edit_id:
                    edit_connector = env['mobilsoft.bank.connector'].sudo().browse(edit_id)
                    if not edit_connector.exists() or edit_connector.company_id.id not in (get_company_ids()):
                        edit_connector = None
        except Exception:
            pass

        values = {
            'page_name': 'ayarlar',
            'connectors': connectors,
            'edit_connector': edit_connector,
            'error': kwargs.get('error', ''),
            'success': kwargs.get('success', ''),
        }
        return request.render('mobilsoft_portal.ayarlar_banka_entegrasyon', values)

    @http.route('/mobilsoft/ayarlar/banka-entegrasyon/kaydet', type='http', auth='user', methods=['POST'], csrf=True, website=True, sitemap=False)
    def banka_entegrasyon_save(self, **kwargs):
        """Banka bağlantısı kaydet."""
        env = request.env
        try:
            if 'mobilsoft.bank.connector' not in env:
                return request.redirect('/mobilsoft/ayarlar/banka-entegrasyon?error=Banka entegrasyon modülü kurulu değil')

            vals = {
                'name': kwargs.get('name', '').strip(),
                'bank_type': kwargs.get('bank_type', ''),
                'api_key': kwargs.get('api_key', '').strip() or False,
                'api_secret': kwargs.get('api_secret', '').strip() or False,
                'active': kwargs.get('active') == 'on',
                'company_id': env.company.id,
            }
            journal_id = int(kwargs.get('journal_id', 0) or 0)
            if journal_id:
                vals['journal_id'] = journal_id

            conn_id = int(kwargs.get('connector_id', 0) or 0)
            if conn_id:
                conn = env['mobilsoft.bank.connector'].sudo().browse(conn_id)
                if conn.exists() and conn.company_id.id in (get_company_ids()):
                    conn.write(vals)
            else:
                env['mobilsoft.bank.connector'].sudo().create(vals)

            return request.redirect('/mobilsoft/ayarlar/banka-entegrasyon?success=Kaydedildi')
        except Exception as e:
            _logger.error('Banka entegrasyon kaydetme hatası: %s', e)
            return request.redirect(f'/mobilsoft/ayarlar/banka-entegrasyon?error={str(e)[:200]}')

    @http.route('/mobilsoft/ayarlar/efatura', type='http', auth='user', website=True, sitemap=False)
    def efatura_settings(self, **kwargs):
        """e-Fatura / e-Arşiv ayarları."""
        env = request.env
        ICP = env['ir.config_parameter'].sudo()

        efatura_settings = {
            'gib_username': ICP.get_param('mobilsoft_qnb_efatura.gib_username', ''),
            'gib_password': ICP.get_param('mobilsoft_qnb_efatura.gib_password', ''),
            'gib_vkn': ICP.get_param('mobilsoft_qnb_efatura.gib_vkn', ''),
            'entegrator': ICP.get_param('mobilsoft_qnb_efatura.entegrator', 'qnb'),
            'efatura_api_url': ICP.get_param('mobilsoft_qnb_efatura.api_url', ''),
            'efatura_api_user': ICP.get_param('mobilsoft_qnb_efatura.api_user', ''),
            'efatura_api_password': ICP.get_param('mobilsoft_qnb_efatura.api_password', ''),
        }

        values = {
            'page_name': 'ayarlar',
            'efatura_settings': efatura_settings,
            'error': kwargs.get('error', ''),
            'success': kwargs.get('success', ''),
        }
        return request.render('mobilsoft_portal.ayarlar_efatura', values)

    @http.route('/mobilsoft/ayarlar/efatura/kaydet', type='http', auth='user', methods=['POST'], csrf=True, website=True, sitemap=False)
    def efatura_save(self, **kwargs):
        """e-Fatura ayarlarını kaydet."""
        env = request.env
        try:
            ICP = env['ir.config_parameter'].sudo()
            ICP.set_param('mobilsoft_qnb_efatura.gib_username', kwargs.get('gib_username', '').strip())
            ICP.set_param('mobilsoft_qnb_efatura.gib_password', kwargs.get('gib_password', '').strip())
            ICP.set_param('mobilsoft_qnb_efatura.gib_vkn', kwargs.get('gib_vkn', '').strip())
            ICP.set_param('mobilsoft_qnb_efatura.entegrator', kwargs.get('entegrator', 'qnb'))
            ICP.set_param('mobilsoft_qnb_efatura.api_url', kwargs.get('efatura_api_url', '').strip())
            ICP.set_param('mobilsoft_qnb_efatura.api_user', kwargs.get('efatura_api_user', '').strip())
            ICP.set_param('mobilsoft_qnb_efatura.api_password', kwargs.get('efatura_api_password', '').strip())

            return request.redirect('/mobilsoft/ayarlar/efatura?success=e-Fatura ayarları kaydedildi')
        except Exception as e:
            _logger.error('e-Fatura ayar kaydetme hatası: %s', e)
            return request.redirect(f'/mobilsoft/ayarlar/efatura?error={str(e)[:200]}')

    # ==================== ŞİFRE DEĞİŞTİR ====================

    @http.route('/mobilsoft/ayarlar/sifre', type='http', auth='user', methods=['POST'], csrf=True, website=True, sitemap=False)
    def sifre_degistir(self, **kwargs):
        new_password = kwargs.get('new_password', '')
        confirm_password = kwargs.get('confirm_password', '')

        if not new_password or len(new_password) < 6:
            return request.redirect('/mobilsoft/ayarlar/profil?error=Şifre en az 6 karakter olmalı')
        if new_password != confirm_password:
            return request.redirect('/mobilsoft/ayarlar/profil?error=Şifreler eşleşmiyor')

        try:
            request.env.user.sudo().password = new_password
            return request.redirect('/mobilsoft/ayarlar/profil?success=Şifre değiştirildi')
        except Exception as e:
            return request.redirect(f'/mobilsoft/ayarlar/profil?error={str(e)[:200]}')
