# -*- coding: utf-8 -*-
"""
MobilSoft Portal — e-Belge Controller
e-Fatura / e-Arşiv / e-İrsaliye listesi ve detayı
"""
import logging
import math

from odoo import http
from odoo.http import request
from .helpers import get_company_ids, get_default_company_id, check_record_access

_logger = logging.getLogger(__name__)

PAGE_SIZE = 20

DOC_TYPE_MAP = {
    'efatura': 'e-Fatura',
    'earsiv': 'e-Arşiv',
    'eirsaliye': 'e-İrsaliye',
    'eirsaliye_yanit': 'e-İrsaliye Yanıtı',
    'uygulama_yanit': 'Uygulama Yanıtı',
}

DOC_STATE_MAP = {
    'draft': 'Taslak',
    'sending': 'Gönderiliyor',
    'sent': 'Gönderildi',
    'delivered': 'Teslim Edildi',
    'accepted': 'Kabul Edildi',
    'rejected': 'Reddedildi',
    'error': 'Hata',
    'cancelled': 'İptal',
}

DOC_STATE_BADGE = {
    'draft': 'bg-secondary',
    'sending': 'bg-info',
    'sent': 'bg-primary',
    'delivered': 'bg-success',
    'accepted': 'bg-success',
    'rejected': 'bg-danger',
    'error': 'bg-danger',
    'cancelled': 'bg-dark',
}


class MobilSoftEBelge(http.Controller):

    # ==================== LİSTE ====================

    @http.route('/mobilsoft/ebelge', type='http', auth='user', website=True, sitemap=False)
    def ebelge_list(self, tab='giden', doc_type='', state='', q='', page='1', **kwargs):
        """e-Belge listesi."""
        env = request.env
        company_ids = get_company_ids()
        page_num = max(1, int(page))

        # QNB modülü yüklü mü kontrol et
        try:
            QnbDoc = env['qnb.document'].sudo()
        except Exception:
            return request.render('mobilsoft_portal.ebelge_list', {
                'page_name': 'ebelge',
                'module_missing': True,
            })

        direction = 'outgoing' if tab != 'gelen' else 'incoming'
        tab = 'giden' if tab != 'gelen' else 'gelen'

        domain = [
            ('company_id', 'in', company_ids),
            ('direction', '=', direction),
        ]

        if doc_type:
            domain.append(('document_type', '=', doc_type))
        if state:
            domain.append(('state', '=', state))
        if q:
            domain.append('|')
            domain.append('|')
            domain.append(('name', 'ilike', q))
            domain.append(('ettn', 'ilike', q))
            domain.append(('partner_id.name', 'ilike', q))

        total = QnbDoc.search_count(domain)
        page_count = max(1, math.ceil(total / PAGE_SIZE))
        page_num = min(page_num, page_count)
        offset = (page_num - 1) * PAGE_SIZE

        documents = QnbDoc.search(domain, limit=PAGE_SIZE, offset=offset, order='document_date desc, id desc')
        page_range = list(range(max(1, page_num - 2), min(page_count, page_num + 2) + 1))

        # İstatistikler
        giden_count = QnbDoc.search_count([('company_id', 'in', company_ids), ('direction', '=', 'outgoing')])
        gelen_count = QnbDoc.search_count([('company_id', 'in', company_ids), ('direction', '=', 'incoming')])

        values = {
            'page_name': 'ebelge',
            'module_missing': False,
            'tab': tab,
            'doc_type_filter': doc_type,
            'state_filter': state,
            'q': q,
            'documents': documents,
            'total': total,
            'page_num': page_num,
            'page_count': page_count,
            'page_range': page_range,
            'giden_count': giden_count,
            'gelen_count': gelen_count,
            'doc_type_map': DOC_TYPE_MAP,
            'doc_state_map': DOC_STATE_MAP,
            'doc_state_badge': DOC_STATE_BADGE,
        }
        return request.render('mobilsoft_portal.ebelge_list', values)

    # ==================== DETAY ====================

    @http.route('/mobilsoft/ebelge/<int:doc_id>', type='http', auth='user', website=True, sitemap=False)
    def ebelge_detail(self, doc_id, **kwargs):
        """e-Belge detay sayfası."""
        env = request.env
        company_ids = get_company_ids()

        try:
            doc = env['qnb.document'].sudo().browse(doc_id)
        except Exception:
            return request.redirect('/mobilsoft/ebelge')

        if not check_record_access(doc):
            return request.redirect('/mobilsoft/ebelge')

        values = {
            'page_name': 'ebelge',
            'doc': doc,
            'doc_type_map': DOC_TYPE_MAP,
            'doc_state_map': DOC_STATE_MAP,
            'doc_state_badge': DOC_STATE_BADGE,
        }
        return request.render('mobilsoft_portal.ebelge_detail', values)
