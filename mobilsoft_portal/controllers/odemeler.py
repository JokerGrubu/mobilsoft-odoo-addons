# -*- coding: utf-8 -*-
"""
MobilSoft Portal — Ödemeler Controller
Tahsilat (müşteriden alınan) ve Ödeme (tedarikçiye yapılan) kayıtları
"""
import logging
import math
from datetime import date

from odoo import http
from odoo.http import request
from .helpers import get_company_ids, get_default_company_id, check_record_access

_logger = logging.getLogger(__name__)

PAGE_SIZE = 20

PAYMENT_TYPE_MAP = {
    'inbound': 'Tahsilat',
    'outbound': 'Ödeme',
}


class MobilSoftOdemeler(http.Controller):

    # ==================== LİSTE ====================

    @http.route('/mobilsoft/odemeler', type='http', auth='user', website=True, sitemap=False)
    def odemeler_list(self, tab='tahsilat', q='', state='', page='1', **kwargs):
        """Ödeme/Tahsilat listesi."""
        env = request.env
        company_ids = get_company_ids()
        page_num = max(1, int(page))

        if tab == 'odeme':
            payment_type = 'outbound'
        else:
            tab = 'tahsilat'
            payment_type = 'inbound'

        domain = [
            ('company_id', 'in', company_ids),
            ('payment_type', '=', payment_type),
        ]

        if state == 'posted':
            domain.append(('state', '=', 'posted'))
        elif state == 'draft':
            domain.append(('state', '=', 'draft'))
        elif state == 'reconciled':
            domain.append(('is_reconciled', '=', True))

        if q:
            domain.append('|')
            domain.append('|')
            domain.append(('name', 'ilike', q))
            domain.append(('partner_id.name', 'ilike', q))
            domain.append(('ref', 'ilike', q))

        Payment = env['account.payment'].sudo()
        total = Payment.search_count(domain)
        page_count = max(1, math.ceil(total / PAGE_SIZE))
        page_num = min(page_num, page_count)
        offset = (page_num - 1) * PAGE_SIZE

        payments = Payment.search(domain, limit=PAGE_SIZE, offset=offset, order='date desc, id desc')

        page_range = list(range(max(1, page_num - 2), min(page_count, page_num + 2) + 1))

        # İstatistikler
        tahsilat_count = Payment.search_count([
            ('company_id', 'in', company_ids),
            ('payment_type', '=', 'inbound'),
        ])
        odeme_count = Payment.search_count([
            ('company_id', 'in', company_ids),
            ('payment_type', '=', 'outbound'),
        ])

        # Bu ay toplam
        today = date.today()
        month_start = today.replace(day=1)
        buay_tahsilat = sum(Payment.search([
            ('company_id', 'in', company_ids),
            ('payment_type', '=', 'inbound'),
            ('state', '=', 'posted'),
            ('date', '>=', str(month_start)),
        ]).mapped('amount'))
        buay_odeme = sum(Payment.search([
            ('company_id', 'in', company_ids),
            ('payment_type', '=', 'outbound'),
            ('state', '=', 'posted'),
            ('date', '>=', str(month_start)),
        ]).mapped('amount'))

        values = {
            'page_name': 'odemeler',
            'tab': tab,
            'q': q,
            'state_filter': state,
            'payments': payments,
            'total': total,
            'page_num': page_num,
            'page_count': page_count,
            'page_range': page_range,
            'tahsilat_count': tahsilat_count,
            'odeme_count': odeme_count,
            'buay_tahsilat': buay_tahsilat,
            'buay_odeme': buay_odeme,
            'payment_type_map': PAYMENT_TYPE_MAP,
        }
        return request.render('mobilsoft_portal.odemeler_list', values)

    # ==================== YENİ ÖDEME/TAHSİLAT ====================

    @http.route('/mobilsoft/odemeler/yeni', type='http', auth='user', website=True, sitemap=False)
    def odeme_form_new(self, payment_type='inbound', partner_id='', invoice_id='', **kwargs):
        """Yeni ödeme/tahsilat formu."""
        env = request.env
        company_ids = get_company_ids()

        # Cari listesi
        partners = env['res.partner'].sudo().search([
            ('company_id', 'in', company_ids + [False]),
            '|', ('customer_rank', '>', 0), ('supplier_rank', '>', 0),
        ], order='name asc')

        # Kasa/Banka hesapları (journal)
        journals = env['account.journal'].sudo().search([
            ('company_id', 'in', company_ids),
            ('type', 'in', ['cash', 'bank']),
        ], order='name asc')

        # Ödenmemiş faturalar (partner_id verilmişse)
        open_invoices = env['account.move']
        selected_partner = False
        selected_invoice = False

        if partner_id:
            partner_id = int(partner_id)
            selected_partner = env['res.partner'].sudo().browse(partner_id)
            if selected_partner.exists():
                inv_type = ['out_invoice'] if payment_type == 'inbound' else ['in_invoice']
                open_invoices = env['account.move'].sudo().search([
                    ('company_id', 'in', company_ids),
                    ('partner_id', '=', partner_id),
                    ('move_type', 'in', inv_type),
                    ('state', '=', 'posted'),
                    ('payment_state', 'in', ['not_paid', 'partial']),
                ], order='invoice_date_due asc')

        if invoice_id:
            invoice_id = int(invoice_id)
            selected_invoice = env['account.move'].sudo().browse(invoice_id)
            if selected_invoice.exists() and not selected_partner:
                selected_partner = selected_invoice.partner_id
                inv_type = ['out_invoice'] if payment_type == 'inbound' else ['in_invoice']
                open_invoices = env['account.move'].sudo().search([
                    ('company_id', 'in', company_ids),
                    ('partner_id', '=', selected_partner.id),
                    ('move_type', 'in', inv_type),
                    ('state', '=', 'posted'),
                    ('payment_state', 'in', ['not_paid', 'partial']),
                ], order='invoice_date_due asc')

        values = {
            'page_name': 'odemeler',
            'payment_type': payment_type,
            'partners': partners,
            'journals': journals,
            'open_invoices': open_invoices,
            'selected_partner': selected_partner,
            'selected_invoice': selected_invoice,
            'error': kwargs.get('error', ''),
            'payment_type_map': PAYMENT_TYPE_MAP,
        }
        return request.render('mobilsoft_portal.odeme_form', values)

    # ==================== KAYDET ====================

    @http.route('/mobilsoft/odemeler/kaydet', type='http', auth='user', methods=['POST'], csrf=True, website=True, sitemap=False)
    def odeme_save(self, **kwargs):
        """Ödeme/Tahsilat kaydet."""
        env = request.env
        company_ids = get_company_ids()

        payment_type = kwargs.get('payment_type', 'inbound')
        partner_id = int(kwargs.get('partner_id', 0))
        journal_id = int(kwargs.get('journal_id', 0))
        amount = float(kwargs.get('amount', 0) or 0)
        payment_date = kwargs.get('date', '')
        ref = kwargs.get('ref', '').strip()
        payment_method = kwargs.get('payment_method', 'nakit')

        if not partner_id or not journal_id or amount <= 0:
            return request.redirect(
                f'/mobilsoft/odemeler/yeni?payment_type={payment_type}'
                f'&error=Cari, hesap ve tutar zorunludur'
            )

        try:
            # Partner type
            partner_type = 'customer' if payment_type == 'inbound' else 'supplier'

            vals = {
                'payment_type': payment_type,
                'partner_type': partner_type,
                'partner_id': partner_id,
                'journal_id': journal_id,
                'amount': amount,
                'company_id': get_default_company_id(),
                'ref': ref or False,
            }

            if payment_date:
                vals['date'] = payment_date

            payment = env['account.payment'].sudo().create(vals)

            # Otomatik onayla
            payment.action_post()

            # Fatura eşleştirme
            invoice_ids = kwargs.get('invoice_ids', '')
            if invoice_ids:
                try:
                    inv_ids = [int(x) for x in invoice_ids.split(',') if x.strip()]
                    if inv_ids:
                        invoices = env['account.move'].sudo().browse(inv_ids)
                        # Reconcile: payment move line ile invoice move line eşleştir
                        payment_lines = payment.move_id.line_ids.filtered(
                            lambda l: l.account_id.account_type in (
                                'asset_receivable', 'liability_payable'
                            )
                        )
                        invoice_lines = invoices.mapped('line_ids').filtered(
                            lambda l: l.account_id.account_type in (
                                'asset_receivable', 'liability_payable'
                            ) and not l.reconciled
                        )
                        if payment_lines and invoice_lines:
                            (payment_lines + invoice_lines).reconcile()
                except Exception as e:
                    _logger.warning('Fatura eşleştirme hatası: %s', e)

            return request.redirect(f'/mobilsoft/odemeler')

        except Exception as e:
            _logger.error('Ödeme oluşturma hatası: %s', e)
            return request.redirect(
                f'/mobilsoft/odemeler/yeni?payment_type={payment_type}'
                f'&partner_id={partner_id}&error={str(e)[:200]}'
            )

    # ==================== FATURADAN ÖDEME AL ====================

    @http.route('/mobilsoft/faturalar/<int:move_id>/odeme-al', type='http', auth='user', website=True, sitemap=False)
    def fatura_odeme_al(self, move_id, **kwargs):
        """Fatura detayından ödeme formuna yönlendir."""
        env = request.env
        invoice = env['account.move'].sudo().browse(move_id)
        if not invoice.exists():
            return request.redirect('/mobilsoft/faturalar')

        payment_type = 'inbound' if invoice.move_type in ['out_invoice'] else 'outbound'
        return request.redirect(
            f'/mobilsoft/odemeler/yeni?payment_type={payment_type}'
            f'&partner_id={invoice.partner_id.id}&invoice_id={invoice.id}'
        )

    # ==================== CARİ ÖDENMEMIŞ FATURALAR (AJAX) ====================

    @http.route('/mobilsoft/odemeler/faturalar', type='http', auth='user', website=True, sitemap=False)
    def get_open_invoices(self, partner_id='0', payment_type='inbound', **kwargs):
        """Cari seçilince ödenmemiş faturaları döndür (basit HTML)."""
        env = request.env
        company_ids = get_company_ids()
        partner_id = int(partner_id)

        if not partner_id:
            return ''

        inv_type = ['out_invoice'] if payment_type == 'inbound' else ['in_invoice']
        invoices = env['account.move'].sudo().search([
            ('company_id', 'in', company_ids),
            ('partner_id', '=', partner_id),
            ('move_type', 'in', inv_type),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ['not_paid', 'partial']),
        ], order='invoice_date_due asc')

        if not invoices:
            return '<div class="text-muted small p-2">Ödenmemiş fatura bulunamadı.</div>'

        html = ''
        for inv in invoices:
            html += f'''
            <div class="form-check py-1 border-bottom">
                <input class="form-check-input invoice-check" type="checkbox"
                       value="{inv.id}" id="inv_{inv.id}" name="inv_{inv.id}">
                <label class="form-check-label small w-100 d-flex justify-content-between" for="inv_{inv.id}">
                    <span>{inv.name} — {inv.partner_id.name}</span>
                    <span class="text-danger fw-bold">₺ {inv.amount_residual:,.2f}</span>
                </label>
            </div>'''
        return html
