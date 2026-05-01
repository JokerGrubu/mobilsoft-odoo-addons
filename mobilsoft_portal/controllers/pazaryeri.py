# -*- coding: utf-8 -*-
"""
MobilSoft Portal — CepteTedarik Pazaryeri Controller
Pazaryeri kanalları, ürünler, siparişler, senkronizasyon logları
"""
import logging

from odoo import http
from odoo.http import request
from .helpers import get_company_ids, get_default_company_id, check_record_access

_logger = logging.getLogger(__name__)


class MobilSoftPazaryeri(http.Controller):

    @http.route('/mobilsoft/pazaryeri', type='http', auth='user', website=True, sitemap=False)
    def pazaryeri_index(self, tab='kanallar', **kwargs):
        """Pazaryeri ana sayfa — kanallar, ürünler, siparişler."""
        env = request.env
        company_ids = get_company_ids()

        # Kanallar
        channels = env['marketplace.channel'].sudo().search([
            ('company_id', 'in', company_ids),
        ], order='name asc')

        # Pazaryeri ürünleri
        mp_products = env['marketplace.product'].sudo().search([
            ('channel_id.company_id', 'in', company_ids),
        ], order='write_date desc', limit=100)

        # Pazaryeri siparişleri
        mp_orders = env['marketplace.order'].sudo().search([
            ('channel_id.company_id', 'in', company_ids),
        ], order='order_date desc', limit=100)

        # Senkronizasyon logları (son 50)
        sync_logs = env['marketplace.sync.log'].sudo().search([
            ('channel_id.company_id', 'in', company_ids),
        ], order='create_date desc', limit=50)

        # İstatistikler
        stats = {
            'channel_count': len(channels),
            'active_channels': len([c for c in channels if c.active]),
            'product_count': len(mp_products),
            'synced_products': len([p for p in mp_products if p.sync_status == 'synced']),
            'order_count': len(mp_orders),
            'pending_orders': len([o for o in mp_orders if not o.synced_to_odoo]),
        }

        values = {
            'page_name': 'pazaryeri',
            'tab': tab,
            'channels': channels,
            'mp_products': mp_products,
            'mp_orders': mp_orders,
            'sync_logs': sync_logs,
            'stats': stats,
            'currency': env.company.currency_id,
        }
        return request.render('mobilsoft_portal.pazaryeri_index', values)

    @http.route('/mobilsoft/pazaryeri/kanal/yeni', type='http', auth='user', website=True, sitemap=False)
    def pazaryeri_kanal_form_new(self, **kwargs):
        """Yeni pazaryeri kanalı formu."""
        env = request.env
        try:
            warehouses = env['stock.warehouse'].sudo().search([
                ('company_id', 'in', get_company_ids()),
            ], order='name asc')
        except Exception:
            warehouses = []

        values = {
            'page_name': 'pazaryeri',
            'channel': None,
            'warehouses': warehouses,
            'error': kwargs.get('error', ''),
            'success': kwargs.get('success', ''),
        }
        return request.render('mobilsoft_portal.pazaryeri_kanal_form', values)

    @http.route('/mobilsoft/pazaryeri/kanal/<int:channel_id>/duzenle', type='http', auth='user', website=True, sitemap=False)
    def pazaryeri_kanal_form_edit(self, channel_id, **kwargs):
        """Kanal düzenleme formu."""
        env = request.env
        channel = env['marketplace.channel'].sudo().browse(channel_id)
        if not channel.exists() or channel.company_id.id not in (get_company_ids()):
            return request.redirect('/mobilsoft/pazaryeri')

        try:
            warehouses = env['stock.warehouse'].sudo().search([
                ('company_id', 'in', get_company_ids()),
            ], order='name asc')
        except Exception:
            warehouses = []

        values = {
            'page_name': 'pazaryeri',
            'channel': channel,
            'warehouses': warehouses,
            'error': kwargs.get('error', ''),
            'success': kwargs.get('success', ''),
        }
        return request.render('mobilsoft_portal.pazaryeri_kanal_form', values)

    @http.route('/mobilsoft/pazaryeri/kanal/kaydet', type='http', auth='user', methods=['POST'], csrf=True, website=True, sitemap=False)
    def pazaryeri_kanal_save(self, **kwargs):
        """Kanal kaydet (yeni veya güncelle)."""
        env = request.env
        try:
            vals = {
                'name': kwargs.get('name', '').strip(),
                'channel_type': kwargs.get('channel_type', ''),
                'api_key': kwargs.get('api_key', '').strip() or False,
                'api_secret': kwargs.get('api_secret', '').strip() or False,
                'merchant_id': kwargs.get('merchant_id', '').strip() or False,
                'shop_id': kwargs.get('shop_id', '').strip() or False,
                'active': kwargs.get('active') == 'on',
                'auto_confirm_orders': kwargs.get('auto_confirm_orders') == 'on',
                'auto_create_picking': kwargs.get('auto_create_picking') == 'on',
                'auto_create_invoice': kwargs.get('auto_create_invoice') == 'on',
                'company_id': env.company.id,
            }
            warehouse_id = int(kwargs.get('warehouse_id', 0) or 0)
            if warehouse_id:
                vals['warehouse_id'] = warehouse_id

            if not vals['name']:
                return request.redirect('/mobilsoft/pazaryeri/kanal/yeni?error=Kanal adı zorunludur')

            channel_id = int(kwargs.get('channel_id', 0) or 0)
            if channel_id:
                channel = env['marketplace.channel'].sudo().browse(channel_id)
                if channel.exists() and channel.company_id.id in (get_company_ids()):
                    channel.write(vals)
                    return request.redirect(f'/mobilsoft/pazaryeri/kanal/{channel.id}?success=Kanal güncellendi')
            else:
                channel = env['marketplace.channel'].sudo().create(vals)
                return request.redirect(f'/mobilsoft/pazaryeri/kanal/{channel.id}?success=Kanal oluşturuldu')

        except Exception as e:
            _logger.error('Kanal kaydetme hatası: %s', e)
            return request.redirect(f'/mobilsoft/pazaryeri/kanal/yeni?error={str(e)[:200]}')

    @http.route('/mobilsoft/pazaryeri/kanal/<int:channel_id>', type='http', auth='user', website=True, sitemap=False)
    def pazaryeri_channel_detail(self, channel_id, **kwargs):
        """Kanal detayı."""
        env = request.env
        channel = env['marketplace.channel'].sudo().browse(channel_id)
        if not channel.exists() or channel.company_id.id not in (get_company_ids()):
            return request.redirect('/mobilsoft/pazaryeri')

        products = env['marketplace.product'].sudo().search([
            ('channel_id', '=', channel.id),
        ], order='write_date desc')

        orders = env['marketplace.order'].sudo().search([
            ('channel_id', '=', channel.id),
        ], order='order_date desc', limit=50)

        values = {
            'page_name': 'pazaryeri',
            'channel': channel,
            'products': products,
            'orders': orders,
            'currency': env.company.currency_id,
        }
        return request.render('mobilsoft_portal.pazaryeri_channel_detail', values)
