# -*- coding: utf-8 -*-
"""
MobilSoft Portal — Dashboard Controller
"""
import logging
from datetime import datetime, date

from odoo import http, _
from odoo.http import request
from .helpers import get_company_ids, get_default_company_id, check_record_access

_logger = logging.getLogger(__name__)


class MobilSoftDashboard(http.Controller):

    @http.route('/mobilsoft/dashboard', type='http', auth='user', website=True, sitemap=False)
    def dashboard(self, **kwargs):
        """Ana dashboard sayfası."""
        env = request.env
        company_ids = get_company_ids()
        today = date.today()
        today_str = today.strftime('%Y-%m-%d')

        # Bugünün satışları
        today_sales = 0
        try:
            orders = env['sale.order'].sudo().search_read(
                [
                    ('company_id', 'in', company_ids),
                    ('date_order', '>=', today_str + ' 00:00:00'),
                    ('state', 'in', ['sale', 'done']),
                ],
                ['amount_total'],
            )
            today_sales = sum(o['amount_total'] or 0 for o in orders)
        except Exception:
            pass

        # Bekleyen faturalar
        pending_invoices = 0
        try:
            pending_invoices = env['account.move'].sudo().search_count([
                ('company_id', 'in', company_ids),
                ('move_type', 'in', ['out_invoice', 'in_invoice']),
                ('payment_state', 'in', ['not_paid', 'partial']),
                ('state', '=', 'posted'),
            ])
        except Exception:
            pass

        # Kritik stok
        stock_alerts = 0
        try:
            stock_alerts = env['product.product'].sudo().search_count([
                ('qty_available', '<=', 0),
                ('type', '=', 'consu'),
            ])
        except Exception:
            pass

        # CepteTedarik yayınlanan ürünler
        ct_products = 0
        try:
            ct_products = env['product.template'].sudo().search_count([
                ('mobilsoft_marketplace_publish', '=', True),
            ])
        except Exception:
            pass

        # Müşteri sayısı
        customer_count = 0
        try:
            customer_count = env['res.partner'].sudo().search_count([
                ('company_id', 'in', company_ids + [False]),
                ('customer_rank', '>', 0),
            ])
        except Exception:
            pass

        # Ürün sayısı
        product_count = 0
        try:
            product_count = env['product.template'].sudo().search_count([
                ('type', '=', 'consu'),
            ])
        except Exception:
            pass

        values = {
            'page_name': 'dashboard',
            'company': env.company,
            'user': env.user,
            'today_str': today.strftime('%d %B %Y'),
            'stats': {
                'today_sales': today_sales,
                'pending_invoices': pending_invoices,
                'stock_alerts': stock_alerts,
                'ct_products': ct_products,
                'customer_count': customer_count,
                'product_count': product_count,
            },
        }
        return request.render('mobilsoft_portal.dashboard_page', values)
