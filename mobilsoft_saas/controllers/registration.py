# -*- coding: utf-8 -*-
"""
MobilSoft SaaS - Kayıt ve Şirket Kurulum Controller

Bu controller, FastAPI backend'den çağrılarak yeni müşteri kaydı sırasında:
1. Yeni Odoo şirketi oluşturur
2. Türk hesap planını (l10n_tr) uygular
3. Kullanıcı oluşturur ve şirkete bağlar
4. Temel günlükleri (kasa, banka) kurar

Auth: 'user' - Odoo admin kullanıcısı çağırır, sudo() ile çalışır.
"""

import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class MobilSoftRegistrationController(http.Controller):

    @http.route('/mobilsoft/register', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def register_company(self, **kwargs):
        """
        Yeni müşteri şirketi oluştur ve kur.

        Parametreler (JSON body):
            company_name (str): Şirket adı (zorunlu)
            user_name (str): Kullanıcı adı (zorunlu)
            email (str): E-posta / login (zorunlu)
            password (str): Şifre (zorunlu)
            vat (str): Vergi numarası (opsiyonel)
            phone (str): Telefon (opsiyonel)
            city (str): Şehir (opsiyonel)
            street (str): Adres (opsiyonel)

        Dönüş:
            {'success': True, 'company_id': int, 'user_id': int, 'message': str}
            {'success': False, 'error': str}
        """
        env = request.env

        company_name = kwargs.get('company_name', '').strip()
        user_name = kwargs.get('user_name', '').strip()
        email = kwargs.get('email', '').strip().lower()
        password = kwargs.get('password', '')

        if not company_name or not email or not password or not user_name:
            return {'success': False, 'error': 'Zorunlu alanlar eksik'}

        # E-posta müsait mi?
        existing = env['res.users'].sudo().search([('login', '=', email)], limit=1)
        if existing:
            return {'success': False, 'error': 'Bu e-posta adresi zaten kullanımda'}

        # Şirket adı müsait mi?
        existing_company = env['res.company'].sudo().search([('name', '=ilike', company_name)], limit=1)
        if existing_company:
            return {'success': False, 'error': 'Bu şirket adı zaten kullanımda'}

        try:
            # ==================== 1. ŞİRKET OLUŞTUR ====================
            tr_country = env['res.country'].sudo().search([('code', '=', 'TR')], limit=1)
            try_currency = env['res.currency'].sudo().search([('name', '=', 'TRY')], limit=1)

            company_vals = {
                'name': company_name,
                'country_id': tr_country.id if tr_country else False,
                'currency_id': try_currency.id if try_currency else False,
            }
            if kwargs.get('vat'):
                company_vals['vat'] = kwargs['vat']
            if kwargs.get('phone'):
                company_vals['phone'] = kwargs['phone']
            if kwargs.get('city'):
                company_vals['city'] = kwargs['city']
            if kwargs.get('street'):
                company_vals['street'] = kwargs['street']
            if kwargs.get('email'):
                company_vals['email'] = email

            company = env['res.company'].sudo().create(company_vals)
            _logger.info('MobilSoft SaaS: Şirket oluşturuldu: %s (ID: %s)', company.name, company.id)

            # ==================== 2. HESAP PLANI YÜKLE ====================
            # Odoo 19'da chart template code tabanlı çalışır (DB kayıt değil)
            # l10n_tr için template code: 'tr'
            try:
                env['account.chart.template'].sudo().try_loading(
                    'tr', company, install_demo=False
                )
                _logger.info('MobilSoft SaaS: Türk hesap planı (l10n_tr) yüklendi.')
            except Exception as e:
                _logger.warning('MobilSoft SaaS: Hesap planı yüklenemedi: %s', e)
                # Hesap planı olmadan devam et - manuel kurulabilir

            # ==================== 3. DEPO OTOMATIK OLUŞUR ====================
            # stock.warehouse, res.company create'de otomatik oluşturulur
            warehouse = env['stock.warehouse'].sudo().search([('company_id', '=', company.id)], limit=1)
            if warehouse:
                _logger.info('MobilSoft SaaS: Depo hazır: %s', warehouse.name)
            else:
                _logger.warning('MobilSoft SaaS: Depo otomatik oluşmadı, manuel oluşturuluyor.')
                env['stock.warehouse'].sudo().create({
                    'name': company_name,
                    'code': company_name[:4].upper(),
                    'company_id': company.id,
                })

            # ==================== 4. KULLANICI OLUŞTUR ====================
            # Temel grup: Dahili Kullanıcı
            # Kullanıcı oluştur (grup ataması ayrı adımda yapılır)
            user_vals = {
                'name': user_name,
                'login': email,
                'password': password,
                'company_id': company.id,
                'company_ids': [(6, 0, [company.id])],
            }

            user = env['res.users'].sudo().create(user_vals)
            _logger.info('MobilSoft SaaS: Kullanıcı oluşturuldu: %s (ID: %s)', user.login, user.id)

            # Grup atamaları - Odoo 19'da field adı group_ids (groups_id değil!)
            # Temel gruplar: Invoicing, Product Manager, Sales, Stock User, Partner Creation
            group_xml_ids = [
                'base.group_user',                # Dahili Kullanıcı (zaten var)
                'base.group_partner_manager',     # Cari/Ortak Oluşturma
                'account.group_account_invoice',  # Faturalama
                'account.group_account_basic',    # Muhasebe Temel
                'product.group_product_manager',  # Ürün Oluşturma
                'product.group_product_variant',  # Ürün Varyant
                'sales_team.group_sale_salesman', # Satış Kullanıcı
                'stock.group_stock_user',         # Stok Kullanıcı
            ]
            groups_to_add = []
            for ref in group_xml_ids:
                g = env.ref(ref, raise_if_not_found=False)
                if g:
                    groups_to_add.append(g.id)
            if groups_to_add:
                try:
                    # Odoo 19: group_ids (not groups_id)
                    user.sudo().write({'group_ids': [(6, 0, groups_to_add)]})
                    _logger.info('MobilSoft SaaS: Gruplar atandı: %s', groups_to_add)
                except Exception as ge:
                    _logger.warning('MobilSoft SaaS: Grup ataması başarısız: %s', ge)

            # ==================== 5. TEMEL GÜNLÜKLER ====================
            # Kasa günlüğü yok ise oluştur
            cash_journal = env['account.journal'].sudo().search([
                ('company_id', '=', company.id),
                ('type', '=', 'cash'),
            ], limit=1)
            if not cash_journal:
                self._create_default_journals(env, company)

            return {
                'success': True,
                'company_id': company.id,
                'user_id': user.id,
                'message': f"'{company_name}' şirketi başarıyla kuruldu. {email} ile giriş yapabilirsiniz.",
            }

        except Exception as e:
            _logger.error('MobilSoft SaaS kayıt hatası: %s', e, exc_info=True)
            # Rollback: Kısmi oluşturulan verileri geri al
            try:
                request.env.cr.rollback()
            except Exception:
                pass
            return {'success': False, 'error': str(e)}

    def _create_default_journals(self, env, company):
        """Temel muhasebe günlüklerini oluştur."""
        # Kasa hesabı bul (101 - Türkiye)
        cash_account = env['account.account'].sudo().search([
            ('company_ids', 'in', [company.id]),
            ('code', 'like', '100'),
        ], limit=1)

        env['account.journal'].sudo().create({
            'name': 'Kasa',
            'type': 'cash',
            'code': 'CSH1',
            'company_id': company.id,
            'default_account_id': cash_account.id if cash_account else False,
        })

        env['account.journal'].sudo().create({
            'name': 'Satışlar',
            'type': 'sale',
            'code': 'SFAT',
            'company_id': company.id,
        })

        env['account.journal'].sudo().create({
            'name': 'Satınalma',
            'type': 'purchase',
            'code': 'AFAT',
            'company_id': company.id,
        })

        _logger.info('MobilSoft SaaS: Temel günlükler oluşturuldu (şirket %s)', company.id)

    @http.route('/mobilsoft/company/setup', type='jsonrpc', auth='user', methods=['POST'], csrf=False)
    def setup_company(self, company_id, **kwargs):
        """
        Mevcut bir şirket için kurulum tamamla.
        (Hesap planı eksikse yükle, depo yoksa oluştur, vs.)
        """
        env = request.env
        company = env['res.company'].sudo().browse(company_id)
        if not company.exists():
            return {'success': False, 'error': 'Şirket bulunamadı'}

        results = {}

        # Hesap planı var mı?
        account_count = env['account.account'].sudo().search_count([
            ('company_ids', 'in', [company_id])
        ])
        results['accounts'] = account_count

        if account_count == 0:
            try:
                env['account.chart.template'].sudo().try_loading(
                    'tr', company, install_demo=False
                )
                results['chart_loaded'] = True
            except Exception as e:
                results['chart_loaded'] = False
                results['chart_error'] = str(e)

        # Depo
        warehouse = env['stock.warehouse'].sudo().search([('company_id', '=', company_id)], limit=1)
        results['warehouse'] = warehouse.name if warehouse else None

        return {'success': True, 'results': results}

    @http.route('/mobilsoft/health', type='http', auth='public', methods=['GET'])
    def health(self):
        """Sağlık kontrolü"""
        return request.make_response(
            json.dumps({'status': 'ok', 'module': 'mobilsoft_saas'}),
            headers=[('Content-Type', 'application/json')]
        )
