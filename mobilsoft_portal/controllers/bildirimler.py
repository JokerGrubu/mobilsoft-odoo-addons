# -*- coding: utf-8 -*-
"""
MobilSoft Portal — Bildirimler Controller
Vade hatırlatmaları, kritik stok uyarıları
"""
import logging
from datetime import date, timedelta

from odoo import http
from odoo.http import request
from .helpers import get_company_ids, get_default_company_id, check_record_access

_logger = logging.getLogger(__name__)


class MobilSoftBildirimler(http.Controller):

    def _get_notifications(self, env, company_ids):
        """Tüm bildirimleri topla."""
        today = date.today()
        notifications = []

        # 1. Vadesi geçmiş faturalar
        overdue_invoices = env['account.move'].sudo().search([
            ('company_id', 'in', company_ids),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ['not_paid', 'partial']),
            ('invoice_date_due', '<', str(today)),
            ('move_type', 'in', ['out_invoice', 'in_invoice']),
        ], order='invoice_date_due asc', limit=50)

        for inv in overdue_invoices:
            days = (today - inv.invoice_date_due).days
            notifications.append({
                'type': 'overdue_invoice',
                'icon': 'fa-file-text-o',
                'color': 'danger',
                'title': f'{inv.name} — Vadesi {days} gün geçti',
                'detail': f'{inv.partner_id.name} — ₺ {inv.amount_residual:,.2f}',
                'url': f'/mobilsoft/faturalar/{inv.id}',
                'date': inv.invoice_date_due,
                'priority': 1,
            })

        # 2. Yaklaşan vade (3 gün içinde)
        soon_invoices = env['account.move'].sudo().search([
            ('company_id', 'in', company_ids),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ['not_paid', 'partial']),
            ('invoice_date_due', '>=', str(today)),
            ('invoice_date_due', '<=', str(today + timedelta(days=3))),
            ('move_type', 'in', ['out_invoice', 'in_invoice']),
        ], limit=30)

        for inv in soon_invoices:
            days = (inv.invoice_date_due - today).days
            notifications.append({
                'type': 'soon_invoice',
                'icon': 'fa-clock-o',
                'color': 'warning',
                'title': f'{inv.name} — {days} gün sonra vadesi dolacak',
                'detail': f'{inv.partner_id.name} — ₺ {inv.amount_residual:,.2f}',
                'url': f'/mobilsoft/faturalar/{inv.id}',
                'date': inv.invoice_date_due,
                'priority': 2,
            })

        # 3. Kritik stok uyarısı (qty_available < 5)
        try:
            low_stock = env['product.product'].sudo().search([
                ('type', '=', 'product'),
                ('qty_available', '<', 5),
                ('qty_available', '>', 0),
            ], limit=20)
            for prod in low_stock:
                notifications.append({
                    'type': 'low_stock',
                    'icon': 'fa-cube',
                    'color': 'info',
                    'title': f'{prod.name} — Stok kritik',
                    'detail': f'Kalan: {prod.qty_available:.0f} {prod.uom_id.name}',
                    'url': f'/mobilsoft/urunler/{prod.id}',
                    'date': today,
                    'priority': 3,
                })
        except Exception:
            pass

        # 4. Çek/Senet vade uyarısı
        try:
            Model = env['mobilsoft.cheque.promissory'].sudo()
            vade_cek = Model.search([
                ('company_id', 'in', company_ids),
                ('state', 'in', ['portfolio', 'deposited']),
                ('maturity_date', '>=', str(today)),
                ('maturity_date', '<=', str(today + timedelta(days=7))),
            ], limit=20)
            for cs in vade_cek:
                days = (cs.maturity_date - today).days
                notifications.append({
                    'type': 'cheque_due',
                    'icon': 'fa-credit-card',
                    'color': 'warning',
                    'title': f'{cs.name} — {days} gün sonra vadesi dolacak',
                    'detail': f'{cs.partner_id.name} — ₺ {cs.amount:,.2f}',
                    'url': f'/mobilsoft/cek-senet/{cs.id}',
                    'date': cs.maturity_date,
                    'priority': 2,
                })
        except Exception:
            pass

        # Sort by priority then date
        notifications.sort(key=lambda x: (x['priority'], x.get('date') or today))
        return notifications

    @http.route('/mobilsoft/bildirimler', type='http', auth='user', website=True, sitemap=False)
    def bildirimler_list(self, **kwargs):
        """Bildirim listesi."""
        env = request.env
        company_ids = get_company_ids()

        notifications = self._get_notifications(env, company_ids)

        values = {
            'page_name': 'bildirimler',
            'notifications': notifications,
            'total': len(notifications),
        }
        return request.render('mobilsoft_portal.bildirimler_list', values)
