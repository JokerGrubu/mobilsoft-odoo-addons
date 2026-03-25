# -*- coding: utf-8 -*-
"""
MobilSoft Portal — Masraflar Controller
Masraf girişi (alış faturası kısayolu) + Çalışan listesi
"""
import logging
import math

from odoo import http
from odoo.http import request
from .helpers import get_company_ids, get_default_company_id, check_record_access

_logger = logging.getLogger(__name__)

PAGE_SIZE = 20

MASRAF_CATEGORIES = [
    ('kira', 'Kira'),
    ('fatura_gider', 'Fatura (Elektrik/Su/Doğalgaz)'),
    ('yakit', 'Yakıt'),
    ('yemek', 'Yemek'),
    ('ulasim', 'Ulaşım'),
    ('ofis', 'Ofis Malzemesi'),
    ('reklam', 'Reklam / Pazarlama'),
    ('bakim', 'Bakım / Onarım'),
    ('diger', 'Diğer'),
]


class MobilSoftMasraflar(http.Controller):

    # ==================== MASRAF LİSTE ====================

    @http.route('/mobilsoft/masraflar', type='http', auth='user', website=True, sitemap=False)
    def masraflar_list(self, page='1', **kwargs):
        """Masraf listesi — alış faturaları (basitleştirilmiş)."""
        env = request.env
        company_ids = get_company_ids()
        page_num = max(1, int(page))

        domain = [
            ('company_id', 'in', company_ids),
            ('move_type', '=', 'in_invoice'),
            ('state', 'in', ['draft', 'posted']),
        ]

        Move = env['account.move'].sudo()
        total = Move.search_count(domain)
        page_count = max(1, math.ceil(total / PAGE_SIZE))
        page_num = min(page_num, page_count)
        offset = (page_num - 1) * PAGE_SIZE

        expenses = Move.search(domain, limit=PAGE_SIZE, offset=offset, order='invoice_date desc, id desc')
        page_range = list(range(max(1, page_num - 2), min(page_count, page_num + 2) + 1))

        # Toplam masraf (bu ay)
        from datetime import date
        today = date.today()
        month_start = today.replace(day=1).isoformat()
        month_total = sum(Move.sudo().search([
            ('company_id', 'in', company_ids),
            ('move_type', '=', 'in_invoice'),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', month_start),
        ]).mapped('amount_total'))

        values = {
            'page_name': 'masraflar',
            'expenses': expenses,
            'total': total,
            'page_num': page_num,
            'page_count': page_count,
            'page_range': page_range,
            'month_total': month_total,
        }
        return request.render('mobilsoft_portal.masraflar_list', values)

    # ==================== MASRAF YENİ ====================

    @http.route('/mobilsoft/masraflar/yeni', type='http', auth='user', website=True, sitemap=False)
    def masraf_form(self, **kwargs):
        """Hızlı masraf giriş formu."""
        env = request.env
        company_ids = get_company_ids()

        suppliers = env['res.partner'].sudo().search([
            ('company_id', 'in', company_ids + [False]),
            ('supplier_rank', '>', 0),
        ], order='name asc')

        taxes = env['account.tax'].sudo().search([
            ('company_id', 'in', company_ids),
            ('type_tax_use', '=', 'purchase'),
        ], order='name asc')

        values = {
            'page_name': 'masraflar',
            'suppliers': suppliers,
            'taxes': taxes,
            'categories': MASRAF_CATEGORIES,
            'error': kwargs.get('error', ''),
        }
        return request.render('mobilsoft_portal.masraf_form', values)

    @http.route('/mobilsoft/masraflar/kaydet', type='http', auth='user', methods=['POST'], csrf=True, website=True, sitemap=False)
    def masraf_save(self, **kwargs):
        """Masraf kaydet (alış faturası olarak)."""
        env = request.env
        company_ids = get_company_ids()

        partner_id = int(kwargs.get('partner_id', 0))
        invoice_date = kwargs.get('invoice_date', '')
        category = kwargs.get('category', 'diger')
        description = kwargs.get('description', '').strip()
        amount = float(kwargs.get('amount', 0) or 0)
        tax_id = int(kwargs.get('tax_id', 0) or 0)

        if not amount:
            return request.redirect('/mobilsoft/masraflar/yeni?error=Tutar zorunludur')

        cat_label = dict(MASRAF_CATEGORIES).get(category, 'Diğer')
        line_name = f"{cat_label}: {description}" if description else cat_label

        line_vals = {
            'name': line_name,
            'quantity': 1,
            'price_unit': amount,
        }
        if tax_id:
            line_vals['tax_ids'] = [(6, 0, [tax_id])]

        try:
            vals = {
                'move_type': 'in_invoice',
                'company_id': get_default_company_id(),
                'invoice_line_ids': [(0, 0, line_vals)],
                'ref': cat_label,
            }
            if partner_id:
                vals['partner_id'] = partner_id
            if invoice_date:
                vals['invoice_date'] = invoice_date

            invoice = env['account.move'].sudo().create(vals)
            return request.redirect(f'/mobilsoft/faturalar/{invoice.id}')
        except Exception as e:
            _logger.error('Masraf kaydetme hatası: %s', e)
            return request.redirect(f'/mobilsoft/masraflar/yeni?error={str(e)[:200]}')

    # ==================== ÇALIŞANLAR ====================

    @http.route('/mobilsoft/calisanlar', type='http', auth='user', website=True, sitemap=False)
    def calisanlar_list(self, **kwargs):
        """Çalışan listesi (res.users bazlı)."""
        env = request.env
        company_ids = get_company_ids()

        users = env['res.users'].sudo().search([
            ('company_id', 'in', company_ids),
            ('active', '=', True),
        ], order='name asc')

        values = {
            'page_name': 'masraflar',
            'users': users,
        }
        return request.render('mobilsoft_portal.calisanlar_list', values)
