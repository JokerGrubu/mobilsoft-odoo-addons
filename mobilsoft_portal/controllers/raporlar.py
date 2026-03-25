# -*- coding: utf-8 -*-
"""
MobilSoft Portal — Raporlar Controller
Gelir/Gider, Kâr/Zarar, Alacak/Borç Yaşlandırma, En Çok Satanlar
"""
import logging
from datetime import date, timedelta
from collections import defaultdict

from odoo import http
from odoo.http import request
from .helpers import get_company_ids, get_default_company_id, check_record_access

_logger = logging.getLogger(__name__)


class MobilSoftRaporlar(http.Controller):

    @http.route('/mobilsoft/raporlar', type='http', auth='user', website=True, sitemap=False)
    def raporlar_index(self, **kwargs):
        """Rapor ana sayfası — rapor seçimi."""
        values = {'page_name': 'raporlar'}
        return request.render('mobilsoft_portal.raporlar_index', values)

    # ==================== GELİR / GİDER ====================

    @http.route('/mobilsoft/raporlar/gelir-gider', type='http', auth='user', website=True, sitemap=False)
    def gelir_gider(self, start='', end='', **kwargs):
        env = request.env
        company_ids = get_company_ids()

        if not end:
            end_date = date.today()
        else:
            end_date = date.fromisoformat(end)
        if not start:
            start_date = end_date.replace(day=1)
        else:
            start_date = date.fromisoformat(start)

        # Gelir (satış faturaları)
        out_invoices = env['account.move'].sudo().search([
            ('company_id', 'in', company_ids),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', start_date.isoformat()),
            ('invoice_date', '<=', end_date.isoformat()),
        ])
        total_gelir = sum(out_invoices.mapped('amount_untaxed'))

        # Gider (alış faturaları)
        in_invoices = env['account.move'].sudo().search([
            ('company_id', 'in', company_ids),
            ('move_type', '=', 'in_invoice'),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', start_date.isoformat()),
            ('invoice_date', '<=', end_date.isoformat()),
        ])
        total_gider = sum(in_invoices.mapped('amount_untaxed'))

        # KDV
        kdv_tahsil = sum(out_invoices.mapped('amount_tax'))
        kdv_odenen = sum(in_invoices.mapped('amount_tax'))

        # Aylık dağılım
        monthly = defaultdict(lambda: {'gelir': 0, 'gider': 0})
        for inv in out_invoices:
            key = inv.invoice_date.strftime('%Y-%m') if inv.invoice_date else 'Belirsiz'
            monthly[key]['gelir'] += inv.amount_untaxed
        for inv in in_invoices:
            key = inv.invoice_date.strftime('%Y-%m') if inv.invoice_date else 'Belirsiz'
            monthly[key]['gider'] += inv.amount_untaxed

        monthly_sorted = sorted(monthly.items())

        values = {
            'page_name': 'raporlar',
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'total_gelir': total_gelir,
            'total_gider': total_gider,
            'net_kar': total_gelir - total_gider,
            'kdv_tahsil': kdv_tahsil,
            'kdv_odenen': kdv_odenen,
            'kdv_fark': kdv_tahsil - kdv_odenen,
            'monthly': monthly_sorted,
        }
        return request.render('mobilsoft_portal.rapor_gelir_gider', values)

    # ==================== ALACAK YAŞLANDIRMA ====================

    @http.route('/mobilsoft/raporlar/alacak-yaslandirma', type='http', auth='user', website=True, sitemap=False)
    def alacak_yaslandirma(self, **kwargs):
        env = request.env
        company_ids = get_company_ids()
        today = date.today()

        # Ödenmemiş satış faturaları
        invoices = env['account.move'].sudo().search([
            ('company_id', 'in', company_ids),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ['not_paid', 'partial']),
        ], order='invoice_date_due asc')

        buckets = {'current': 0, '1_30': 0, '31_60': 0, '61_90': 0, '90_plus': 0}
        rows = []

        for inv in invoices:
            due = inv.invoice_date_due or inv.invoice_date or today
            days = (today - due).days
            residual = inv.amount_residual

            if days <= 0:
                bucket = 'current'
            elif days <= 30:
                bucket = '1_30'
            elif days <= 60:
                bucket = '31_60'
            elif days <= 90:
                bucket = '61_90'
            else:
                bucket = '90_plus'

            buckets[bucket] += residual
            rows.append({
                'invoice': inv,
                'days': max(0, days),
                'bucket': bucket,
                'residual': residual,
            })

        values = {
            'page_name': 'raporlar',
            'buckets': buckets,
            'total': sum(buckets.values()),
            'rows': rows,
        }
        return request.render('mobilsoft_portal.rapor_alacak_yaslandirma', values)

    # ==================== EN ÇOK SATANLAR ====================

    @http.route('/mobilsoft/raporlar/en-cok-satanlar', type='http', auth='user', website=True, sitemap=False)
    def en_cok_satanlar(self, start='', end='', **kwargs):
        env = request.env
        company_ids = get_company_ids()

        if not end:
            end_date = date.today()
        else:
            end_date = date.fromisoformat(end)
        if not start:
            start_date = end_date - timedelta(days=30)
        else:
            start_date = date.fromisoformat(start)

        # Satış siparişleri satırları
        sale_lines = env['sale.order.line'].sudo().search([
            ('company_id', 'in', company_ids),
            ('order_id.state', 'in', ['sale', 'done']),
            ('order_id.date_order', '>=', start_date.isoformat()),
            ('order_id.date_order', '<=', end_date.isoformat() + ' 23:59:59'),
            ('product_id', '!=', False),
        ])

        product_stats = defaultdict(lambda: {'qty': 0, 'total': 0, 'name': '', 'code': ''})
        for sl in sale_lines:
            pid = sl.product_id.id
            product_stats[pid]['qty'] += sl.product_uom_qty
            product_stats[pid]['total'] += sl.price_subtotal
            product_stats[pid]['name'] = sl.product_id.name
            product_stats[pid]['code'] = sl.product_id.default_code or ''

        # Sırala (ciroya göre)
        top_products = sorted(product_stats.values(), key=lambda x: x['total'], reverse=True)[:20]

        # En çok satan müşteriler
        partner_stats = defaultdict(lambda: {'total': 0, 'count': 0, 'name': ''})
        orders = env['sale.order'].sudo().search([
            ('company_id', 'in', company_ids),
            ('state', 'in', ['sale', 'done']),
            ('date_order', '>=', start_date.isoformat()),
            ('date_order', '<=', end_date.isoformat() + ' 23:59:59'),
        ])
        for o in orders:
            pid = o.partner_id.id
            partner_stats[pid]['total'] += o.amount_total
            partner_stats[pid]['count'] += 1
            partner_stats[pid]['name'] = o.partner_id.name

        top_customers = sorted(partner_stats.values(), key=lambda x: x['total'], reverse=True)[:10]

        values = {
            'page_name': 'raporlar',
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'top_products': top_products,
            'top_customers': top_customers,
        }
        return request.render('mobilsoft_portal.rapor_en_cok_satanlar', values)
