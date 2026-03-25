# -*- coding: utf-8 -*-
"""
MobilSoft Portal — Teklif + Sipariş Controller
"""
import logging
import math

from odoo import http
from odoo.http import request
from .helpers import get_company_ids, get_default_company_id, check_record_access

_logger = logging.getLogger(__name__)

PAGE_SIZE = 20

STATE_MAP = {
    'draft': 'Teklif',
    'sent': 'Gönderildi',
    'sale': 'Sipariş',
    'done': 'Kilitli',
    'cancel': 'İptal',
}


class MobilSoftSiparisler(http.Controller):

    # ==================== LİSTE ====================

    @http.route('/mobilsoft/siparisler', type='http', auth='user', website=True, sitemap=False)
    def siparisler_list(self, tab='teklif', q='', page='1', **kwargs):
        """Teklif + Sipariş listesi."""
        env = request.env
        company_ids = get_company_ids()
        page_num = max(1, int(page))

        domain = [('company_id', 'in', company_ids)]

        if tab == 'siparis':
            domain.append(('state', 'in', ['sale', 'done']))
        else:
            tab = 'teklif'
            domain.append(('state', 'in', ['draft', 'sent']))

        if q:
            domain.append('|')
            domain.append(('name', 'ilike', q))
            domain.append(('partner_id.name', 'ilike', q))

        Order = env['sale.order'].sudo()
        total = Order.search_count(domain)
        page_count = max(1, math.ceil(total / PAGE_SIZE))
        page_num = min(page_num, page_count)
        offset = (page_num - 1) * PAGE_SIZE

        orders = Order.search(domain, limit=PAGE_SIZE, offset=offset, order='create_date desc')
        page_range = list(range(max(1, page_num - 2), min(page_count, page_num + 2) + 1))

        teklif_count = Order.search_count([('company_id', 'in', company_ids), ('state', 'in', ['draft', 'sent'])])
        siparis_count = Order.search_count([('company_id', 'in', company_ids), ('state', 'in', ['sale', 'done'])])

        values = {
            'page_name': 'siparisler',
            'tab': tab,
            'q': q,
            'orders': orders,
            'total': total,
            'page_num': page_num,
            'page_count': page_count,
            'page_range': page_range,
            'teklif_count': teklif_count,
            'siparis_count': siparis_count,
            'state_map': STATE_MAP,
        }
        return request.render('mobilsoft_portal.siparisler_list', values)

    # ==================== DETAY ====================

    @http.route('/mobilsoft/siparisler/<int:order_id>', type='http', auth='user', website=True, sitemap=False)
    def siparis_detail(self, order_id, **kwargs):
        """Sipariş/Teklif detay."""
        env = request.env
        company_ids = get_company_ids()

        order = env['sale.order'].sudo().browse(order_id)
        if not check_record_access(order):
            return request.redirect('/mobilsoft/siparisler')

        values = {
            'page_name': 'siparisler',
            'order': order,
            'lines': order.order_line,
            'state_map': STATE_MAP,
        }
        return request.render('mobilsoft_portal.siparis_detail', values)

    # ==================== YENİ TEKLİF ====================

    @http.route('/mobilsoft/siparisler/yeni', type='http', auth='user', website=True, sitemap=False)
    def siparis_form_new(self, **kwargs):
        """Yeni teklif formu."""
        env = request.env
        company_ids = get_company_ids()

        partners = env['res.partner'].sudo().search([
            ('company_id', 'in', company_ids + [False]),
            ('customer_rank', '>', 0),
        ], order='name asc')

        # Products are SHARED — no company filter
        products = env['product.product'].sudo().search(
            [], order='name asc', limit=200)

        taxes = env['account.tax'].sudo().search([
            ('company_id', 'in', company_ids),
            ('type_tax_use', '=', 'sale'),
        ], order='name asc')

        values = {
            'page_name': 'siparisler',
            'partners': partners,
            'products': products,
            'taxes': taxes,
            'error': kwargs.get('error', ''),
        }
        return request.render('mobilsoft_portal.siparis_form', values)

    @http.route('/mobilsoft/siparisler/kaydet', type='http', auth='user', methods=['POST'], csrf=True, website=True, sitemap=False)
    def siparis_save(self, **kwargs):
        """Teklif kaydet."""
        env = request.env
        company_ids = get_company_ids()

        partner_id = int(kwargs.get('partner_id', 0))
        validity_date = kwargs.get('validity_date', '')
        note = kwargs.get('note', '').strip()

        if not partner_id:
            return request.redirect('/mobilsoft/siparisler/yeni?error=Müşteri seçimi zorunludur')

        # Satırları topla
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
                'product_uom_qty': qty,
                'price_unit': price,
            }
            if product_id:
                line_vals['product_id'] = product_id
            if description:
                line_vals['name'] = description
            elif not product_id:
                line_vals['name'] = 'Kalem'
            if tax_id:
                line_vals['tax_id'] = [(6, 0, [tax_id])]

            line_ids.append((0, 0, line_vals))
            idx += 1

        if not line_ids:
            return request.redirect('/mobilsoft/siparisler/yeni?error=En az bir satır ekleyin')

        try:
            vals = {
                'partner_id': partner_id,
                'company_id': get_default_company_id(),
                'order_line': line_ids,
                'note': note or False,
            }
            if validity_date:
                vals['validity_date'] = validity_date

            order = env['sale.order'].sudo().create(vals)
            return request.redirect(f'/mobilsoft/siparisler/{order.id}')
        except Exception as e:
            _logger.error('Sipariş oluşturma hatası: %s', e)
            return request.redirect(f'/mobilsoft/siparisler/yeni?error={str(e)[:200]}')

    # ==================== ONAYLA (Teklif → Sipariş) ====================

    @http.route('/mobilsoft/siparisler/<int:order_id>/onayla', type='http', auth='user', methods=['POST'], csrf=True, website=True, sitemap=False)
    def siparis_onayla(self, order_id, **kwargs):
        """Teklifi siparişe çevir."""
        env = request.env
        order = env['sale.order'].sudo().browse(order_id)
        if order.exists() and order.state in ['draft', 'sent']:
            try:
                order.action_confirm()
            except Exception as e:
                _logger.error('Sipariş onaylama hatası: %s', e)
        return request.redirect(f'/mobilsoft/siparisler/{order_id}')

    # ==================== SİPARİŞTEN FATURA OLUŞTUR ====================

    @http.route('/mobilsoft/siparisler/<int:order_id>/fatura-olustur', type='http', auth='user', methods=['POST'], csrf=True, website=True, sitemap=False)
    def siparis_fatura_olustur(self, order_id, **kwargs):
        """Siparişten fatura oluştur."""
        env = request.env
        order = env['sale.order'].sudo().browse(order_id)
        if order.exists() and order.state == 'sale':
            try:
                invoice = order._create_invoices()
                if invoice:
                    return request.redirect(f'/mobilsoft/faturalar/{invoice[0].id}')
            except Exception as e:
                _logger.error('Fatura oluşturma hatası: %s', e)
        return request.redirect(f'/mobilsoft/siparisler/{order_id}')

    # ==================== SİPARİŞTEN İRSALİYE GÖRÜNTÜLE ====================

    @http.route('/mobilsoft/siparisler/<int:order_id>/irsaliyeler', type='http', auth='user', website=True, sitemap=False)
    def siparis_irsaliyeler(self, order_id, **kwargs):
        """Siparişin irsaliyelerine yönlendir."""
        env = request.env
        order = env['sale.order'].sudo().browse(order_id)
        if order.exists() and order.picking_ids:
            return request.redirect(f'/mobilsoft/irsaliyeler/{order.picking_ids[0].id}')
        return request.redirect(f'/mobilsoft/siparisler/{order_id}')
