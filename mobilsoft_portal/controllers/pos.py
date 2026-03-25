# -*- coding: utf-8 -*-
"""
MobilSoft Portal — POS (Kasa) Controller
POS yapılandırmaları, oturumlar, satış siparişleri
"""
import logging

from odoo import http
from odoo.http import request
from .helpers import get_company_ids, get_default_company_id, check_record_access

_logger = logging.getLogger(__name__)


class MobilSoftPOS(http.Controller):

    @http.route('/mobilsoft/pos', type='http', auth='user', website=True, sitemap=False)
    def pos_index(self, **kwargs):
        """POS ana sayfa — kasalar, oturumlar, siparişler."""
        env = request.env
        company_ids = get_company_ids()

        # POS Kasaları (kullanıcının erişebildiği tüm şirketler)
        configs = env['pos.config'].sudo().search([
            ('company_id', 'in', company_ids),
        ], order='name asc')

        # Açık oturumlar
        open_sessions = env['pos.session'].sudo().search([
            ('config_id.company_id', 'in', company_ids),
            ('state', 'in', ['opening_control', 'opened']),
        ], order='start_at desc')

        # Kapalı oturumlar (son 20)
        closed_sessions = env['pos.session'].sudo().search([
            ('config_id.company_id', 'in', company_ids),
            ('state', 'in', ['closing_control', 'closed']),
        ], order='stop_at desc', limit=20)

        # Son siparişler (son 50)
        orders = env['pos.order'].sudo().search([
            ('company_id', 'in', company_ids),
        ], order='date_order desc', limit=50)

        # İstatistikler
        total_orders = env['pos.order'].sudo().search_count([
            ('company_id', 'in', company_ids),
        ])
        today_orders = env['pos.order'].sudo().search([
            ('company_id', 'in', company_ids),
            ('date_order', '>=', str(__import__('datetime').date.today())),
        ])
        today_revenue = sum(o.amount_total for o in today_orders)

        # Ödeme yöntemleri
        payment_methods = env['pos.payment.method'].sudo().search([
            ('company_id', 'in', company_ids),
        ], order='name asc')

        values = {
            'page_name': 'pos',
            'configs': configs,
            'open_sessions': open_sessions,
            'closed_sessions': closed_sessions,
            'orders': orders,
            'total_orders': total_orders,
            'today_count': len(today_orders),
            'today_revenue': today_revenue,
            'payment_methods': payment_methods,
            'currency': env.company.currency_id,
        }
        return request.render('mobilsoft_portal.pos_index', values)

    @http.route('/mobilsoft/pos/oturum-ac', type='http', auth='user', methods=['POST'], csrf=True, website=True, sitemap=False)
    def pos_session_open(self, **kwargs):
        """POS oturumu aç."""
        env = request.env
        try:
            config_id = int(kwargs.get('config_id', 0) or 0)
            if not config_id:
                return request.redirect('/mobilsoft/pos?error=Kasa seçilmedi')

            config = env['pos.config'].sudo().browse(config_id)
            if not config.exists() or config.company_id.id not in get_company_ids():
                return request.redirect('/mobilsoft/pos?error=Geçersiz kasa')

            # Check if session already open
            existing = env['pos.session'].sudo().search([
                ('config_id', '=', config.id),
                ('state', 'in', ['opening_control', 'opened']),
            ], limit=1)
            if existing:
                return request.redirect('/mobilsoft/pos?error=Bu kasada zaten açık bir oturum var')

            session = env['pos.session'].sudo().create({
                'config_id': config.id,
                'user_id': env.user.id,
            })
            return request.redirect(f'/mobilsoft/pos?success=Oturum açıldı: {session.name}')
        except Exception as e:
            _logger.error('POS oturum açma hatası: %s', e)
            return request.redirect(f'/mobilsoft/pos?error={str(e)[:200]}')

    @http.route('/mobilsoft/pos/oturum-kapat/<int:session_id>', type='http', auth='user', methods=['POST'], csrf=True, website=True, sitemap=False)
    def pos_session_close(self, session_id, **kwargs):
        """POS oturumu kapat."""
        env = request.env
        try:
            session = env['pos.session'].sudo().browse(session_id)
            if not session.exists() or session.config_id.company_id.id not in get_company_ids():
                return request.redirect('/mobilsoft/pos?error=Geçersiz oturum')

            if session.state not in ('opening_control', 'opened'):
                return request.redirect('/mobilsoft/pos?error=Oturum zaten kapalı')

            session.action_pos_session_closing_control()
            return request.redirect(f'/mobilsoft/pos?success=Oturum kapatıldı: {session.name}')
        except Exception as e:
            _logger.error('POS oturum kapatma hatası: %s', e)
            return request.redirect(f'/mobilsoft/pos?error={str(e)[:200]}')

    @http.route('/mobilsoft/pos/siparis/<int:order_id>', type='http', auth='user', website=True, sitemap=False)
    def pos_order_detail(self, order_id, **kwargs):
        """POS sipariş detayı."""
        env = request.env
        order = env['pos.order'].sudo().browse(order_id)
        if not order.exists() or order.company_id.id not in get_company_ids():
            return request.redirect('/mobilsoft/pos')

        values = {
            'page_name': 'pos',
            'order': order,
            'currency': env.company.currency_id,
        }
        return request.render('mobilsoft_portal.pos_order_detail', values)
