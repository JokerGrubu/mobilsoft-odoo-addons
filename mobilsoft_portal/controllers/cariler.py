# -*- coding: utf-8 -*-
"""
MobilSoft Portal — Cariler Controller
Müşteri + Tedarikçi yönetimi
"""
import logging
import math
from datetime import date, timedelta

from odoo import http
from odoo.http import request
from .helpers import get_company_ids, get_default_company_id, check_record_access

_logger = logging.getLogger(__name__)

PAGE_SIZE = 20


class MobilSoftCariler(http.Controller):

    # ==================== LİSTE ====================

    @http.route('/mobilsoft/cariler', type='http', auth='user', website=True, sitemap=False)
    def cariler_list(self, tab='musteri', q='', page='1', **kwargs):
        """Cari listesi — müşteri/tedarikçi sekmeleri, arama, sayfalama."""
        env = request.env
        company_ids = get_company_ids()
        page_num = max(1, int(page))

        domain = [('company_id', 'in', company_ids + [False])]

        if tab == 'tedarikci':
            domain.append(('supplier_rank', '>', 0))
        else:
            tab = 'musteri'
            domain.append(('customer_rank', '>', 0))

        if q:
            domain.append('|')
            domain.append(('name', 'ilike', q))
            domain.append(('vat', 'ilike', q))

        Partner = env['res.partner'].sudo()
        total = Partner.search_count(domain)
        page_count = max(1, math.ceil(total / PAGE_SIZE))
        page_num = min(page_num, page_count)
        offset = (page_num - 1) * PAGE_SIZE

        partners = Partner.search(domain, limit=PAGE_SIZE, offset=offset, order='name asc')

        # Bakiye bilgisi — alacak/borç
        partner_balances = {}
        try:
            for p in partners:
                receivable = sum(
                    env['account.move.line'].sudo().search([
                        ('partner_id', '=', p.id),
                        ('account_id.account_type', '=', 'asset_receivable'),
                        ('parent_state', '=', 'posted'),
                        ('company_id', 'in', company_ids),
                    ]).mapped('amount_residual')
                )
                payable = sum(
                    env['account.move.line'].sudo().search([
                        ('partner_id', '=', p.id),
                        ('account_id.account_type', '=', 'liability_payable'),
                        ('parent_state', '=', 'posted'),
                        ('company_id', 'in', company_ids),
                    ]).mapped('amount_residual')
                )
                partner_balances[p.id] = {
                    'receivable': receivable,
                    'payable': abs(payable),
                    'net': receivable + payable,
                }
        except Exception as e:
            _logger.warning('Cari bakiye hesaplama hatası: %s', e)

        # Sayfa sayıları (gösterilecek)
        page_range = []
        start = max(1, page_num - 2)
        end = min(page_count, page_num + 2)
        for i in range(start, end + 1):
            page_range.append(i)

        # Toplam istatistikler
        musteri_count = Partner.search_count([
            ('company_id', 'in', company_ids + [False]),
            ('customer_rank', '>', 0),
        ])
        tedarikci_count = Partner.search_count([
            ('company_id', 'in', company_ids + [False]),
            ('supplier_rank', '>', 0),
        ])

        values = {
            'page_name': 'cariler',
            'tab': tab,
            'q': q,
            'partners': partners,
            'partner_balances': partner_balances,
            'total': total,
            'page_num': page_num,
            'page_count': page_count,
            'page_range': page_range,
            'page_size': PAGE_SIZE,
            'musteri_count': musteri_count,
            'tedarikci_count': tedarikci_count,
        }
        return request.render('mobilsoft_portal.cariler_list', values)

    # ==================== DETAY ====================

    @http.route('/mobilsoft/cariler/<int:partner_id>', type='http', auth='user', website=True, sitemap=False)
    def cari_detail(self, partner_id, **kwargs):
        """Cari detay sayfası."""
        env = request.env
        company_ids = get_company_ids()

        partner = env['res.partner'].sudo().browse(partner_id)
        if not partner.exists():
            return request.redirect('/mobilsoft/cariler')

        # Bakiye
        receivable = sum(
            env['account.move.line'].sudo().search([
                ('partner_id', '=', partner_id),
                ('account_id.account_type', '=', 'asset_receivable'),
                ('parent_state', '=', 'posted'),
                ('company_id', 'in', company_ids),
            ]).mapped('amount_residual')
        )
        payable = sum(
            env['account.move.line'].sudo().search([
                ('partner_id', '=', partner_id),
                ('account_id.account_type', '=', 'liability_payable'),
                ('parent_state', '=', 'posted'),
                ('company_id', 'in', company_ids),
            ]).mapped('amount_residual')
        )

        # Son faturalar
        invoices = env['account.move'].sudo().search([
            ('partner_id', '=', partner_id),
            ('company_id', 'in', company_ids),
            ('move_type', 'in', ['out_invoice', 'in_invoice', 'out_refund', 'in_refund']),
            ('state', '=', 'posted'),
        ], limit=10, order='invoice_date desc')

        # Son siparişler
        orders = env['sale.order'].sudo().search([
            ('partner_id', '=', partner_id),
            ('company_id', 'in', company_ids),
        ], limit=10, order='date_order desc')

        values = {
            'page_name': 'cariler',
            'partner': partner,
            'receivable': receivable,
            'payable': abs(payable),
            'net_balance': receivable + payable,
            'invoices': invoices,
            'orders': orders,
        }
        return request.render('mobilsoft_portal.cari_detail', values)

    # ==================== OLUŞTUR / DÜZENLE ====================

    @http.route('/mobilsoft/cariler/yeni', type='http', auth='user', website=True, sitemap=False)
    def cari_form_new(self, **kwargs):
        """Yeni cari formu."""
        env = request.env
        values = {
            'page_name': 'cariler',
            'partner': None,
            'is_edit': False,
            'error': kwargs.get('error', ''),
            'countries': env['res.country'].sudo().search([], order='name asc'),
            'states': [],
        }
        return request.render('mobilsoft_portal.cari_form', values)

    @http.route('/mobilsoft/cariler/<int:partner_id>/duzenle', type='http', auth='user', website=True, sitemap=False)
    def cari_form_edit(self, partner_id, **kwargs):
        """Cari düzenleme formu."""
        env = request.env
        partner = env['res.partner'].sudo().browse(partner_id)
        if not partner.exists():
            return request.redirect('/mobilsoft/cariler')

        country_id = partner.country_id.id if partner.country_id else False
        states = []
        if country_id:
            states = env['res.country.state'].sudo().search([('country_id', '=', country_id)], order='name asc')

        values = {
            'page_name': 'cariler',
            'partner': partner,
            'is_edit': True,
            'error': kwargs.get('error', ''),
            'countries': env['res.country'].sudo().search([], order='name asc'),
            'states': states,
        }
        return request.render('mobilsoft_portal.cari_form', values)

    @http.route('/mobilsoft/cariler/kaydet', type='http', auth='user', methods=['POST'], csrf=True, website=True, sitemap=False)
    def cari_save(self, **kwargs):
        """Cari kaydet (yeni veya düzenle)."""
        env = request.env
        company_ids = get_company_ids()

        partner_id = int(kwargs.get('partner_id', 0))
        name = kwargs.get('name', '').strip()
        vat = kwargs.get('vat', '').strip()
        phone = kwargs.get('phone', '').strip()
        # mobile alanı Odoo 19'da kaldırıldı
        email = kwargs.get('email', '').strip()
        street = kwargs.get('street', '').strip()
        city = kwargs.get('city', '').strip()
        country_id = int(kwargs.get('country_id', 0)) or False
        state_id = int(kwargs.get('state_id', 0)) or False
        zip_code = kwargs.get('zip', '').strip()
        cari_type = kwargs.get('cari_type', 'musteri')
        company_type = kwargs.get('company_type', 'company')

        if not name:
            return request.redirect('/mobilsoft/cariler/yeni?error=İsim zorunludur')

        vals = {
            'name': name,
            'vat': vat or False,
            'phone': phone or False,
            'email': email or False,
            'street': street or False,
            'city': city or False,
            'country_id': country_id,
            'state_id': state_id,
            'zip': zip_code or False,
            'company_type': company_type,
        }

        if cari_type == 'tedarikci':
            vals['supplier_rank'] = 1
        else:
            vals['customer_rank'] = 1

        try:
            if partner_id:
                partner = env['res.partner'].sudo().browse(partner_id)
                if partner.exists():
                    partner.write(vals)
            else:
                vals['company_id'] = get_default_company_id()
                partner = env['res.partner'].sudo().create(vals)
                partner_id = partner.id

            return request.redirect(f'/mobilsoft/cariler/{partner_id}')
        except Exception as e:
            _logger.error('Cari kaydetme hatası: %s', e)
            return request.redirect('/mobilsoft/cariler/yeni?error=Kaydetme hatası')

    # ==================== EKSTRE ====================

    @http.route('/mobilsoft/cariler/<int:partner_id>/ekstre', type='http', auth='user', website=True, sitemap=False)
    def cari_ekstre(self, partner_id, start='', end='', **kwargs):
        """Cari ekstre — hesap hareketleri."""
        env = request.env
        company_ids = get_company_ids()

        partner = env['res.partner'].sudo().browse(partner_id)
        if not partner.exists():
            return request.redirect('/mobilsoft/cariler')

        # Varsayılan: son 3 ay
        if not end:
            end_date = date.today()
        else:
            end_date = date.fromisoformat(end)

        if not start:
            start_date = end_date - timedelta(days=90)
        else:
            start_date = date.fromisoformat(start)

        domain = [
            ('partner_id', '=', partner_id),
            ('company_id', 'in', company_ids),
            ('parent_state', '=', 'posted'),
            ('date', '>=', start_date.isoformat()),
            ('date', '<=', end_date.isoformat()),
            ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
        ]

        move_lines = env['account.move.line'].sudo().search(domain, order='date asc, id asc')

        # Açılış bakiyesi — start_date öncesi
        opening_domain = [
            ('partner_id', '=', partner_id),
            ('company_id', 'in', company_ids),
            ('parent_state', '=', 'posted'),
            ('date', '<', start_date.isoformat()),
            ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
        ]
        opening_lines = env['account.move.line'].sudo().search(opening_domain)
        opening_balance = sum(opening_lines.mapped('balance'))

        # Hareketleri formatla
        lines = []
        running = opening_balance
        for ml in move_lines:
            running += ml.balance
            lines.append({
                'date': ml.date,
                'ref': ml.move_id.name or '',
                'description': ml.name or ml.move_id.ref or '',
                'debit': ml.debit,
                'credit': ml.credit,
                'balance': running,
            })

        values = {
            'page_name': 'cariler',
            'partner': partner,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'opening_balance': opening_balance,
            'lines': lines,
            'closing_balance': running,
        }
        return request.render('mobilsoft_portal.cari_ekstre', values)

    # ==================== CARİ MUTABAKAT ====================

    @http.route('/mobilsoft/cariler/<int:partner_id>/mutabakat', type='http', auth='user', website=True, sitemap=False)
    def cari_mutabakat(self, partner_id, start_date='', end_date='', **kwargs):
        """Cari mutabakat mektubu sayfası."""
        env = request.env
        company_ids = get_company_ids()
        partner = env['res.partner'].sudo().browse(partner_id)
        if not partner.exists():
            return request.redirect('/mobilsoft/cariler')

        today = date.today()
        if not start_date:
            start_date = today.replace(month=1, day=1)
        else:
            start_date = date.fromisoformat(start_date)
        if not end_date:
            end_date = today
        else:
            end_date = date.fromisoformat(end_date)

        # Hareket satırları
        MoveLine = env['account.move.line'].sudo()
        lines = MoveLine.search([
            ('partner_id', '=', partner_id),
            ('company_id', 'in', company_ids),
            ('parent_state', '=', 'posted'),
            ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
            ('date', '>=', str(start_date)),
            ('date', '<=', str(end_date)),
        ], order='date asc, id asc')

        # Açılış bakiyesi
        opening_lines = MoveLine.search([
            ('partner_id', '=', partner_id),
            ('company_id', 'in', company_ids),
            ('parent_state', '=', 'posted'),
            ('account_id.account_type', 'in', ['asset_receivable', 'liability_payable']),
            ('date', '<', str(start_date)),
        ])
        opening_balance = sum(opening_lines.mapped('debit')) - sum(opening_lines.mapped('credit'))

        total_debit = sum(lines.mapped('debit'))
        total_credit = sum(lines.mapped('credit'))
        closing_balance = opening_balance + total_debit - total_credit

        company = env.company

        values = {
            'page_name': 'cariler',
            'partner': partner,
            'company': company,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'opening_balance': opening_balance,
            'lines': lines,
            'total_debit': total_debit,
            'total_credit': total_credit,
            'closing_balance': closing_balance,
        }
        return request.render('mobilsoft_portal.cari_mutabakat', values)
