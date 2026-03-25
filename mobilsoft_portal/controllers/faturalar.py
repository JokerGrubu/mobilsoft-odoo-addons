# -*- coding: utf-8 -*-
"""
MobilSoft Portal — Faturalar Controller
Satış/Alış faturaları, iade faturaları
"""
import logging
import math
from datetime import date, timedelta

from odoo import http
from odoo.http import request
from odoo.exceptions import AccessDenied, UserError
from .helpers import get_company_ids, get_default_company_id, check_record_access
import base64

_logger = logging.getLogger(__name__)

PAGE_SIZE = 20

MOVE_TYPE_MAP = {
    'out_invoice': 'Satış Faturası',
    'in_invoice': 'Alış Faturası',
    'out_refund': 'Satış İadesi',
    'in_refund': 'Alış İadesi',
}


class MobilSoftFaturalar(http.Controller):

    # ==================== LİSTE ====================

    @http.route('/mobilsoft/faturalar', type='http', auth='user', website=True, sitemap=False)
    def faturalar_list(self, tab='satis', q='', state='', page='1', **kwargs):
        """Fatura listesi."""
        env = request.env
        company_ids = get_company_ids()
        page_num = max(1, int(page))

        # Tab → move_type
        if tab == 'alis':
            move_types = ['in_invoice', 'in_refund']
        else:
            tab = 'satis'
            move_types = ['out_invoice', 'out_refund']

        domain = [
            ('company_id', 'in', company_ids),
            ('move_type', 'in', move_types),
        ]

        if state == 'paid':
            domain.append(('payment_state', '=', 'paid'))
        elif state == 'not_paid':
            domain.append(('payment_state', 'in', ['not_paid', 'partial']))
            domain.append(('state', '=', 'posted'))
        elif state == 'draft':
            domain.append(('state', '=', 'draft'))
        elif state == 'posted':
            domain.append(('state', '=', 'posted'))

        if q:
            domain.append('|')
            domain.append('|')
            domain.append(('name', 'ilike', q))
            domain.append(('partner_id.name', 'ilike', q))
            domain.append(('ref', 'ilike', q))

        Move = env['account.move'].sudo()
        total = Move.search_count(domain)
        page_count = max(1, math.ceil(total / PAGE_SIZE))
        page_num = min(page_num, page_count)
        offset = (page_num - 1) * PAGE_SIZE

        invoices = Move.search(domain, limit=PAGE_SIZE, offset=offset, order='invoice_date desc, id desc')

        page_range = list(range(max(1, page_num - 2), min(page_count, page_num + 2) + 1))

        # İstatistikler
        satis_count = Move.search_count([
            ('company_id', 'in', company_ids),
            ('move_type', 'in', ['out_invoice', 'out_refund']),
        ])
        alis_count = Move.search_count([
            ('company_id', 'in', company_ids),
            ('move_type', 'in', ['in_invoice', 'in_refund']),
        ])
        bekleyen = Move.search_count([
            ('company_id', 'in', company_ids),
            ('move_type', 'in', move_types),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ['not_paid', 'partial']),
        ])

        values = {
            'page_name': 'faturalar',
            'tab': tab,
            'q': q,
            'state_filter': state,
            'invoices': invoices,
            'total': total,
            'page_num': page_num,
            'page_count': page_count,
            'page_range': page_range,
            'satis_count': satis_count,
            'alis_count': alis_count,
            'bekleyen': bekleyen,
            'move_type_map': MOVE_TYPE_MAP,
        }
        return request.render('mobilsoft_portal.faturalar_list', values)

    # ==================== DETAY ====================

    @http.route('/mobilsoft/faturalar/<int:move_id>', type='http', auth='user', website=True, sitemap=False)
    def fatura_detail(self, move_id, **kwargs):
        """Fatura detay sayfası."""
        env = request.env
        company_ids = get_company_ids()

        invoice = env['account.move'].sudo().browse(move_id)
        if not check_record_access(invoice):
            return request.redirect('/mobilsoft/faturalar')

        values = {
            'page_name': 'faturalar',
            'invoice': invoice,
            'lines': invoice.invoice_line_ids,
            'move_type_map': MOVE_TYPE_MAP,
        }
        return request.render('mobilsoft_portal.fatura_detail', values)

    # ==================== YENİ FATURA ====================

    @http.route('/mobilsoft/faturalar/yeni', type='http', auth='user', website=True, sitemap=False)
    def fatura_form_new(self, move_type='out_invoice', **kwargs):
        """Yeni fatura formu."""
        env = request.env
        company_ids = get_company_ids()

        # Cari listesi
        if move_type in ['out_invoice', 'out_refund']:
            partners = env['res.partner'].sudo().search([
                ('company_id', 'in', company_ids + [False]),
                ('customer_rank', '>', 0),
            ], order='name asc')
        else:
            partners = env['res.partner'].sudo().search([
                ('company_id', 'in', company_ids + [False]),
                ('supplier_rank', '>', 0),
            ], order='name asc')

        # Products are SHARED — no company filter
        products = env['product.product'].sudo().search(
            [], order='name asc', limit=200)

        tax_type = 'sale' if move_type in ['out_invoice', 'out_refund'] else 'purchase'
        taxes = env['account.tax'].sudo().search([
            ('company_id', 'in', company_ids),
            ('type_tax_use', '=', tax_type),
        ], order='name asc')

        # Döviz listesi
        currencies = env['res.currency'].sudo().search([('active', '=', True)], order='name asc')
        company_currency = env.company.currency_id

        values = {
            'page_name': 'faturalar',
            'move_type': move_type,
            'partners': partners,
            'products': products,
            'taxes': taxes,
            'currencies': currencies,
            'company_currency': company_currency,
            'error': kwargs.get('error', ''),
            'move_type_map': MOVE_TYPE_MAP,
        }
        return request.render('mobilsoft_portal.fatura_form', values)

    @http.route('/mobilsoft/faturalar/kaydet', type='http', auth='user', methods=['POST'], csrf=True, website=True, sitemap=False)
    def fatura_save(self, **kwargs):
        """Fatura kaydet (taslak olarak)."""
        env = request.env
        company_ids = get_company_ids()

        move_type = kwargs.get('move_type', 'out_invoice')
        partner_id = int(kwargs.get('partner_id', 0))
        invoice_date = kwargs.get('invoice_date', '')
        ref = kwargs.get('ref', '').strip()

        if not partner_id:
            return request.redirect(f'/mobilsoft/faturalar/yeni?move_type={move_type}&error=Cari seçimi zorunludur')

        # Fatura satırlarını topla
        line_ids = []
        idx = 0
        while True:
            product_key = f'line_product_{idx}'
            if product_key not in kwargs:
                break
            product_id = int(kwargs.get(product_key, 0))
            qty = float(kwargs.get(f'line_qty_{idx}', 1) or 1)
            price = float(kwargs.get(f'line_price_{idx}', 0) or 0)
            description = kwargs.get(f'line_desc_{idx}', '').strip()
            tax_id = int(kwargs.get(f'line_tax_{idx}', 0) or 0)

            line_vals = {
                'quantity': qty,
                'price_unit': price,
            }
            if product_id:
                line_vals['product_id'] = product_id
            if description:
                line_vals['name'] = description
            if tax_id:
                line_vals['tax_ids'] = [(6, 0, [tax_id])]

            line_ids.append((0, 0, line_vals))
            idx += 1

        if not line_ids:
            return request.redirect(f'/mobilsoft/faturalar/yeni?move_type={move_type}&error=En az bir satır ekleyin')

        try:
            currency_id = int(kwargs.get('currency_id', 0) or 0)

            vals = {
                'move_type': move_type,
                'partner_id': partner_id,
                'company_id': get_default_company_id(),
                'invoice_line_ids': line_ids,
                'ref': ref or False,
            }
            if currency_id:
                vals['currency_id'] = currency_id
            if invoice_date:
                vals['invoice_date'] = invoice_date

            invoice = env['account.move'].sudo().create(vals)
            return request.redirect(f'/mobilsoft/faturalar/{invoice.id}')
        except Exception as e:
            _logger.error('Fatura oluşturma hatası: %s', e)
            return request.redirect(f'/mobilsoft/faturalar/yeni?move_type={move_type}&error={str(e)[:200]}')

    # ==================== FATURA ONAYLA ====================

    @http.route('/mobilsoft/faturalar/<int:move_id>/onayla', type='http', auth='user', methods=['POST'], csrf=True, website=True, sitemap=False)
    def fatura_onayla(self, move_id, **kwargs):
        """Faturayı onayla (taslak → onaylı)."""
        env = request.env
        invoice = env['account.move'].sudo().browse(move_id)
        if invoice.exists() and invoice.state == 'draft':
            try:
                invoice.action_post()
            except Exception as e:
                _logger.error('Fatura onaylama hatası: %s', e)
        return request.redirect(f'/mobilsoft/faturalar/{move_id}')

    # ==================== PDF İNDİR ====================

    @http.route('/mobilsoft/faturalar/<int:move_id>/pdf', type='http', auth='user', website=True, sitemap=False)
    def fatura_pdf(self, move_id, **kwargs):
        """Fatura PDF indirme."""
        env = request.env
        company_ids = get_company_ids()
        invoice = env['account.move'].sudo().browse(move_id)

        if not check_record_access(invoice):
            return request.redirect('/mobilsoft/faturalar')

        try:
            # Odoo'nun standart fatura raporunu kullan
            report = env.ref('account.account_invoices')
            pdf_content, content_type = report.sudo()._render_qweb_pdf(
                report.id, [invoice.id]
            )

            filename = f"{invoice.name or 'fatura'}.pdf".replace('/', '_')
            headers = [
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'attachment; filename="{filename}"'),
                ('Content-Length', str(len(pdf_content))),
            ]
            return request.make_response(pdf_content, headers=headers)
        except Exception as e:
            _logger.error('PDF oluşturma hatası: %s', e)
            return request.redirect(f'/mobilsoft/faturalar/{move_id}')
