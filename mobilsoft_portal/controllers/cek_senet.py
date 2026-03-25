# -*- coding: utf-8 -*-
"""
MobilSoft Portal — Çek/Senet Controller
mobilsoft.cheque.promissory modeli üzerinden portal erişimi
"""
import logging
import math
from datetime import date, timedelta

from odoo import http
from odoo.http import request
from .helpers import get_company_ids, get_default_company_id, check_record_access

_logger = logging.getLogger(__name__)

PAGE_SIZE = 20

DOC_TYPE_MAP = {
    'cheque': 'Çek',
    'promissory': 'Senet',
}

DIRECTION_MAP = {
    'received': 'Alınan',
    'given': 'Verilen',
}

STATE_MAP = {
    'portfolio': 'Portföyde',
    'endorsed': 'Ciro Edildi',
    'deposited': 'Tahsile Verildi',
    'collected': 'Tahsil Edildi',
    'returned': 'İade Edildi',
    'bounced': 'Karşılıksız',
    'cancelled': 'İptal',
}

STATE_BADGE = {
    'portfolio': 'bg-primary',
    'endorsed': 'bg-info',
    'deposited': 'bg-warning',
    'collected': 'bg-success',
    'returned': 'bg-secondary',
    'bounced': 'bg-danger',
    'cancelled': 'bg-dark',
}


class MobilSoftCekSenet(http.Controller):

    @http.route('/mobilsoft/cek-senet', type='http', auth='user', website=True, sitemap=False)
    def cek_senet_list(self, tab='alinan', doc_type='', state='', q='', page='1', **kwargs):
        """Çek/Senet listesi."""
        env = request.env
        company_ids = get_company_ids()
        page_num = max(1, int(page))

        try:
            Model = env['mobilsoft.cheque.promissory'].sudo()
        except Exception:
            return request.render('mobilsoft_portal.cek_senet_list', {
                'page_name': 'cek_senet',
                'module_missing': True,
            })

        direction = 'received' if tab != 'verilen' else 'given'
        tab = 'alinan' if tab != 'verilen' else 'verilen'

        domain = [
            ('company_id', 'in', company_ids),
            ('direction', '=', direction),
        ]

        if doc_type:
            domain.append(('type', '=', doc_type))
        if state:
            domain.append(('state', '=', state))
        if q:
            domain.append('|')
            domain.append('|')
            domain.append(('name', 'ilike', q))
            domain.append(('partner_id.name', 'ilike', q))
            domain.append(('bank_id.name', 'ilike', q))

        total = Model.search_count(domain)
        page_count = max(1, math.ceil(total / PAGE_SIZE))
        page_num = min(page_num, page_count)
        offset = (page_num - 1) * PAGE_SIZE

        records = Model.search(domain, limit=PAGE_SIZE, offset=offset, order='maturity_date asc, id desc')
        page_range = list(range(max(1, page_num - 2), min(page_count, page_num + 2) + 1))

        # İstatistikler
        alinan_count = Model.search_count([('company_id', 'in', company_ids), ('direction', '=', 'received')])
        verilen_count = Model.search_count([('company_id', 'in', company_ids), ('direction', '=', 'given')])

        # Vade yaklaşanlar (7 gün içinde)
        today = date.today()
        week_later = today + timedelta(days=7)
        vade_yaklasan = Model.search_count([
            ('company_id', 'in', company_ids),
            ('state', 'in', ['portfolio', 'deposited']),
            ('maturity_date', '>=', str(today)),
            ('maturity_date', '<=', str(week_later)),
        ])

        values = {
            'page_name': 'cek_senet',
            'module_missing': False,
            'tab': tab,
            'doc_type_filter': doc_type,
            'state_filter': state,
            'q': q,
            'records': records,
            'total': total,
            'page_num': page_num,
            'page_count': page_count,
            'page_range': page_range,
            'alinan_count': alinan_count,
            'verilen_count': verilen_count,
            'vade_yaklasan': vade_yaklasan,
            'doc_type_map': DOC_TYPE_MAP,
            'direction_map': DIRECTION_MAP,
            'state_map': STATE_MAP,
            'state_badge': STATE_BADGE,
        }
        return request.render('mobilsoft_portal.cek_senet_list', values)

    @http.route('/mobilsoft/cek-senet/<int:rec_id>', type='http', auth='user', website=True, sitemap=False)
    def cek_senet_detail(self, rec_id, **kwargs):
        """Çek/Senet detay."""
        env = request.env
        company_ids = get_company_ids()

        try:
            rec = env['mobilsoft.cheque.promissory'].sudo().browse(rec_id)
        except Exception:
            return request.redirect('/mobilsoft/cek-senet')

        if not check_record_access(rec):
            return request.redirect('/mobilsoft/cek-senet')

        values = {
            'page_name': 'cek_senet',
            'rec': rec,
            'doc_type_map': DOC_TYPE_MAP,
            'direction_map': DIRECTION_MAP,
            'state_map': STATE_MAP,
            'state_badge': STATE_BADGE,
        }
        return request.render('mobilsoft_portal.cek_senet_detail', values)
