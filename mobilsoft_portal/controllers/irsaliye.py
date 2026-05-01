# -*- coding: utf-8 -*-
"""
MobilSoft Portal — İrsaliye Controller
stock.picking üzerinden sevk irsaliyesi listesi/detayı
"""
import logging
import math

from odoo import http
from odoo.http import request
from .helpers import get_company_ids, get_default_company_id, check_record_access

_logger = logging.getLogger(__name__)

PAGE_SIZE = 20

PICKING_STATE_MAP = {
    'draft': 'Taslak',
    'waiting': 'Bekliyor',
    'confirmed': 'Onaylandı',
    'assigned': 'Hazır',
    'done': 'Tamamlandı',
    'cancel': 'İptal',
}

PICKING_STATE_BADGE = {
    'draft': 'bg-secondary',
    'waiting': 'bg-warning',
    'confirmed': 'bg-info',
    'assigned': 'bg-primary',
    'done': 'bg-success',
    'cancel': 'bg-dark',
}


class MobilSoftIrsaliye(http.Controller):

    @http.route('/mobilsoft/irsaliyeler', type='http', auth='user', website=True, sitemap=False)
    def irsaliye_list(self, tab='giden', q='', state='', page='1', **kwargs):
        """İrsaliye listesi."""
        env = request.env
        company_ids = get_company_ids()
        page_num = max(1, int(page))

        # Giden: out (delivery) / Gelen: in (receipts)
        Picking = env['stock.picking'].sudo()

        # Picking type'ları bul
        if tab == 'gelen':
            picking_types = env['stock.picking.type'].sudo().search([
                ('company_id', 'in', company_ids),
                ('code', '=', 'incoming'),
            ])
        else:
            tab = 'giden'
            picking_types = env['stock.picking.type'].sudo().search([
                ('company_id', 'in', company_ids),
                ('code', '=', 'outgoing'),
            ])

        domain = [
            ('company_id', 'in', company_ids),
            ('picking_type_id', 'in', picking_types.ids),
        ]

        if state:
            domain.append(('state', '=', state))
        if q:
            domain.append('|')
            domain.append(('name', 'ilike', q))
            domain.append(('partner_id.name', 'ilike', q))

        total = Picking.search_count(domain)
        page_count = max(1, math.ceil(total / PAGE_SIZE))
        page_num = min(page_num, page_count)
        offset = (page_num - 1) * PAGE_SIZE

        pickings = Picking.search(domain, limit=PAGE_SIZE, offset=offset, order='scheduled_date desc, id desc')
        page_range = list(range(max(1, page_num - 2), min(page_count, page_num + 2) + 1))

        # İstatistikler
        giden_types = env['stock.picking.type'].sudo().search([
            ('company_id', 'in', company_ids), ('code', '=', 'outgoing')])
        gelen_types = env['stock.picking.type'].sudo().search([
            ('company_id', 'in', company_ids), ('code', '=', 'incoming')])
        giden_count = Picking.search_count([
            ('company_id', 'in', company_ids), ('picking_type_id', 'in', giden_types.ids)])
        gelen_count = Picking.search_count([
            ('company_id', 'in', company_ids), ('picking_type_id', 'in', gelen_types.ids)])

        values = {
            'page_name': 'irsaliyeler',
            'tab': tab,
            'q': q,
            'state_filter': state,
            'pickings': pickings,
            'total': total,
            'page_num': page_num,
            'page_count': page_count,
            'page_range': page_range,
            'giden_count': giden_count,
            'gelen_count': gelen_count,
            'state_map': PICKING_STATE_MAP,
            'state_badge': PICKING_STATE_BADGE,
        }
        return request.render('mobilsoft_portal.irsaliye_list', values)

    @http.route('/mobilsoft/irsaliyeler/<int:picking_id>', type='http', auth='user', website=True, sitemap=False)
    def irsaliye_detail(self, picking_id, **kwargs):
        """İrsaliye detay."""
        env = request.env
        company_ids = get_company_ids()
        picking = env['stock.picking'].sudo().browse(picking_id)

        if not check_record_access(picking):
            return request.redirect('/mobilsoft/irsaliyeler')

        values = {
            'page_name': 'irsaliyeler',
            'picking': picking,
            'lines': picking.move_ids,
            'state_map': PICKING_STATE_MAP,
            'state_badge': PICKING_STATE_BADGE,
        }
        return request.render('mobilsoft_portal.irsaliye_detail', values)
