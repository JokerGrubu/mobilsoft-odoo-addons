# -*- coding: utf-8 -*-
"""
MobilSoft Portal — Ürünler + Stok Controller
"""
import logging
import math
import base64

from odoo import http
from odoo.http import request
from .helpers import get_company_ids, get_default_company_id, check_record_access

_logger = logging.getLogger(__name__)

PAGE_SIZE = 20


class MobilSoftUrunler(http.Controller):

    # ==================== LİSTE ====================

    @http.route('/mobilsoft/urunler', type='http', auth='user', website=True, sitemap=False)
    def urunler_list(self, q='', category='', page='1', **kwargs):
        """Ürün listesi — arama, kategori filtre, stok bilgisi."""
        env = request.env
        company_ids = get_company_ids()
        page_num = max(1, int(page))

        # Products are SHARED — no company filter
        domain = []

        if q:
            domain.append('|')
            domain.append('|')
            domain.append(('name', 'ilike', q))
            domain.append(('default_code', 'ilike', q))
            domain.append(('barcode', 'ilike', q))

        category_id = int(category) if category else 0
        if category_id:
            domain.append(('categ_id', '=', category_id))

        Product = env['product.template'].sudo()
        total = Product.search_count(domain)
        page_count = max(1, math.ceil(total / PAGE_SIZE))
        page_num = min(page_num, page_count)
        offset = (page_num - 1) * PAGE_SIZE

        products = Product.search(domain, limit=PAGE_SIZE, offset=offset, order='name asc')

        # Kategoriler
        categories = env['product.category'].sudo().search([], order='name asc')

        # Sayfa aralığı
        page_range = list(range(max(1, page_num - 2), min(page_count, page_num + 2) + 1))

        # İstatistikler
        total_products = Product.search_count([])
        low_stock = 0
        try:
            low_stock = env['product.product'].sudo().search_count([
                ('qty_available', '<=', 0),
                ('type', '=', 'consu'),
            ])
        except Exception:
            pass

        values = {
            'page_name': 'urunler',
            'q': q,
            'category': category_id,
            'products': products,
            'categories': categories,
            'total': total,
            'page_num': page_num,
            'page_count': page_count,
            'page_range': page_range,
            'total_products': total_products,
            'low_stock': low_stock,
        }
        return request.render('mobilsoft_portal.urunler_list', values)

    # ==================== DETAY ====================

    @http.route('/mobilsoft/urunler/<int:product_id>', type='http', auth='user', website=True, sitemap=False)
    def urun_detail(self, product_id, **kwargs):
        """Ürün detay sayfası."""
        env = request.env
        company_ids = get_company_ids()

        product = env['product.template'].sudo().browse(product_id)
        if not product.exists():
            return request.redirect('/mobilsoft/urunler')

        # Stok bilgisi (varyantlar üzerinden)
        variants = product.product_variant_ids
        stock_info = []
        total_qty = 0
        for v in variants:
            qty = v.qty_available
            total_qty += qty
            stock_info.append({
                'name': v.display_name,
                'qty': qty,
                'virtual_qty': v.virtual_available,
            })

        # Son satış hareketleri
        recent_sales = []
        try:
            sale_lines = env['sale.order.line'].sudo().search([
                ('product_id', 'in', variants.ids),
                ('company_id', 'in', company_ids),
                ('order_id.state', 'in', ['sale', 'done']),
            ], limit=10, order='create_date desc')
            for sl in sale_lines:
                recent_sales.append({
                    'date': sl.order_id.date_order,
                    'partner': sl.order_id.partner_id.name,
                    'qty': sl.product_uom_qty,
                    'price': sl.price_unit,
                    'total': sl.price_subtotal,
                })
        except Exception:
            pass

        values = {
            'page_name': 'urunler',
            'product': product,
            'stock_info': stock_info,
            'total_qty': total_qty,
            'recent_sales': recent_sales,
        }
        return request.render('mobilsoft_portal.urun_detail', values)

    # ==================== OLUŞTUR / DÜZENLE ====================

    @http.route('/mobilsoft/urunler/yeni', type='http', auth='user', website=True, sitemap=False)
    def urun_form_new(self, **kwargs):
        """Yeni ürün formu."""
        env = request.env
        values = {
            'page_name': 'urunler',
            'product': None,
            'is_edit': False,
            'error': kwargs.get('error', ''),
            'categories': env['product.category'].sudo().search([], order='name asc'),
            'uom_list': env['uom.uom'].sudo().search([], order='name asc'),
            'tax_list': env['account.tax'].sudo().search([
                ('company_id', 'in', get_company_ids()),
                ('type_tax_use', '=', 'sale'),
            ], order='name asc'),
        }
        return request.render('mobilsoft_portal.urun_form', values)

    @http.route('/mobilsoft/urunler/<int:product_id>/duzenle', type='http', auth='user', website=True, sitemap=False)
    def urun_form_edit(self, product_id, **kwargs):
        """Ürün düzenleme formu."""
        env = request.env
        product = env['product.template'].sudo().browse(product_id)
        if not product.exists():
            return request.redirect('/mobilsoft/urunler')

        values = {
            'page_name': 'urunler',
            'product': product,
            'is_edit': True,
            'error': kwargs.get('error', ''),
            'categories': env['product.category'].sudo().search([], order='name asc'),
            'uom_list': env['uom.uom'].sudo().search([], order='name asc'),
            'tax_list': env['account.tax'].sudo().search([
                ('company_id', 'in', get_company_ids()),
                ('type_tax_use', '=', 'sale'),
            ], order='name asc'),
        }
        return request.render('mobilsoft_portal.urun_form', values)

    @http.route('/mobilsoft/urunler/kaydet', type='http', auth='user', methods=['POST'], csrf=True, website=True, sitemap=False)
    def urun_save(self, **kwargs):
        """Ürün kaydet."""
        env = request.env
        company_ids = get_company_ids()

        product_id = int(kwargs.get('product_id', 0))
        name = kwargs.get('name', '').strip()
        default_code = kwargs.get('default_code', '').strip()
        barcode = kwargs.get('barcode', '').strip()
        list_price = float(kwargs.get('list_price', 0) or 0)
        standard_price = float(kwargs.get('standard_price', 0) or 0)
        categ_id = int(kwargs.get('categ_id', 0)) or False
        uom_id = int(kwargs.get('uom_id', 0)) or False
        product_type = kwargs.get('type', 'consu')
        description = kwargs.get('description_sale', '').strip()

        if not name:
            return request.redirect('/mobilsoft/urunler/yeni?error=Ürün adı zorunludur')

        vals = {
            'name': name,
            'default_code': default_code or False,
            'barcode': barcode or False,
            'list_price': list_price,
            'standard_price': standard_price,
            'type': product_type,
            'description_sale': description or False,
        }
        if categ_id:
            vals['categ_id'] = categ_id
        if uom_id:
            vals['uom_id'] = uom_id
            vals['uom_po_id'] = uom_id

        # Vergi
        tax_ids = kwargs.getlist('tax_ids') if hasattr(kwargs, 'getlist') else []
        if not tax_ids:
            tax_id = kwargs.get('tax_ids', '')
            if tax_id:
                tax_ids = [tax_id]
        if tax_ids:
            vals['taxes_id'] = [(6, 0, [int(t) for t in tax_ids if t])]

        # Resim
        image_file = kwargs.get('image')
        if image_file and hasattr(image_file, 'read'):
            image_data = image_file.read()
            if image_data:
                vals['image_1920'] = base64.b64encode(image_data)

        try:
            if product_id:
                product = env['product.template'].sudo().browse(product_id)
                if product.exists():
                    product.write(vals)
            else:
                vals['company_id'] = get_default_company_id()
                product = env['product.template'].sudo().create(vals)
                product_id = product.id

            return request.redirect(f'/mobilsoft/urunler/{product_id}')
        except Exception as e:
            _logger.error('Ürün kaydetme hatası: %s', e)
            return request.redirect('/mobilsoft/urunler/yeni?error=Kaydetme hatası: %s' % str(e))

    # ==================== STOK HAREKETLERİ ====================

    @http.route('/mobilsoft/urunler/<int:product_id>/stok', type='http', auth='user', website=True, sitemap=False)
    def urun_stok(self, product_id, **kwargs):
        """Ürün stok hareketleri."""
        env = request.env
        company_ids = get_company_ids()

        product = env['product.template'].sudo().browse(product_id)
        if not product.exists():
            return request.redirect('/mobilsoft/urunler')

        variant_ids = product.product_variant_ids.ids

        # Stok hareketleri
        moves = env['stock.move'].sudo().search([
            ('product_id', 'in', variant_ids),
            ('state', '=', 'done'),
        ], limit=50, order='date desc')

        move_lines = []
        for m in moves:
            move_lines.append({
                'date': m.date,
                'reference': m.reference or m.name,
                'origin': m.origin or '',
                'from': m.location_id.display_name,
                'to': m.location_dest_id.display_name,
                'qty': m.quantity,
                'uom': m.product_uom.name if m.product_uom else '',
            })

        values = {
            'page_name': 'urunler',
            'product': product,
            'move_lines': move_lines,
            'total_qty': sum(v.qty_available for v in product.product_variant_ids),
        }
        return request.render('mobilsoft_portal.urun_stok', values)
