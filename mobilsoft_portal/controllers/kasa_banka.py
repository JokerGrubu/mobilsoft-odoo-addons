# -*- coding: utf-8 -*-
"""
MobilSoft Portal — Kasa + Banka Controller
"""
import logging
import math
from datetime import date, timedelta

from odoo import http
from odoo.http import request
from .helpers import get_company_ids, get_default_company_id, check_record_access

_logger = logging.getLogger(__name__)

PAGE_SIZE = 20


class MobilSoftKasaBanka(http.Controller):

    # ==================== ANA SAYFA ====================

    @http.route('/mobilsoft/kasa-banka', type='http', auth='user', website=True, sitemap=False)
    def kasa_banka_list(self, **kwargs):
        """Kasa ve banka hesapları listesi."""
        env = request.env
        company_ids = get_company_ids()

        # Kasa ve banka günlükleri (journals)
        journals = env['account.journal'].sudo().search([
            ('company_id', 'in', company_ids),
            ('type', 'in', ['cash', 'bank']),
        ], order='type, name')

        journal_data = []
        for j in journals:
            # Bakiye hesapla
            balance = 0
            try:
                lines = env['account.move.line'].sudo().search([
                    ('journal_id', '=', j.id),
                    ('parent_state', '=', 'posted'),
                    ('account_id', '=', j.default_account_id.id),
                ])
                balance = sum(lines.mapped('balance'))
            except Exception:
                pass

            journal_data.append({
                'journal': j,
                'balance': balance,
                'type_label': 'Kasa' if j.type == 'cash' else 'Banka',
                'icon': 'fa-money' if j.type == 'cash' else 'fa-university',
            })

        total_cash = sum(d['balance'] for d in journal_data if d['journal'].type == 'cash')
        total_bank = sum(d['balance'] for d in journal_data if d['journal'].type == 'bank')

        values = {
            'page_name': 'kasa_banka',
            'journal_data': journal_data,
            'total_cash': total_cash,
            'total_bank': total_bank,
            'total_all': total_cash + total_bank,
        }
        return request.render('mobilsoft_portal.kasa_banka_list', values)

    # ==================== HESAP DETAY ====================

    @http.route('/mobilsoft/kasa-banka/<int:journal_id>', type='http', auth='user', website=True, sitemap=False)
    def kasa_banka_detail(self, journal_id, start='', end='', page='1', **kwargs):
        """Kasa/Banka hesap hareketleri."""
        env = request.env
        company_ids = get_company_ids()
        page_num = max(1, int(page))

        journal = env['account.journal'].sudo().browse(journal_id)
        if not check_record_access(journal):
            return request.redirect('/mobilsoft/kasa-banka')

        # Tarih aralığı
        if not end:
            end_date = date.today()
        else:
            end_date = date.fromisoformat(end)
        if not start:
            start_date = end_date - timedelta(days=30)
        else:
            start_date = date.fromisoformat(start)

        domain = [
            ('journal_id', '=', journal_id),
            ('parent_state', '=', 'posted'),
            ('account_id', '=', journal.default_account_id.id),
            ('date', '>=', start_date.isoformat()),
            ('date', '<=', end_date.isoformat()),
        ]

        MLine = env['account.move.line'].sudo()
        total = MLine.search_count(domain)
        page_count = max(1, math.ceil(total / PAGE_SIZE))
        page_num = min(page_num, page_count)
        offset = (page_num - 1) * PAGE_SIZE

        move_lines = MLine.search(domain, limit=PAGE_SIZE, offset=offset, order='date desc, id desc')
        page_range = list(range(max(1, page_num - 2), min(page_count, page_num + 2) + 1))

        # Güncel bakiye
        all_lines = MLine.search([
            ('journal_id', '=', journal_id),
            ('parent_state', '=', 'posted'),
            ('account_id', '=', journal.default_account_id.id),
        ])
        current_balance = sum(all_lines.mapped('balance'))

        # Dönem giriş/çıkış
        period_lines = MLine.search([
            ('journal_id', '=', journal_id),
            ('parent_state', '=', 'posted'),
            ('account_id', '=', journal.default_account_id.id),
            ('date', '>=', start_date.isoformat()),
            ('date', '<=', end_date.isoformat()),
        ])
        total_in = sum(l.debit for l in period_lines)
        total_out = sum(l.credit for l in period_lines)

        values = {
            'page_name': 'kasa_banka',
            'journal': journal,
            'move_lines': move_lines,
            'current_balance': current_balance,
            'total_in': total_in,
            'total_out': total_out,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'total': total,
            'page_num': page_num,
            'page_count': page_count,
            'page_range': page_range,
        }
        return request.render('mobilsoft_portal.kasa_banka_detail', values)
