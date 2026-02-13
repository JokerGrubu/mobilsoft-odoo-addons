# -*- coding: utf-8 -*-

from datetime import timedelta
import logging

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BankConnector(models.Model):
    """Turkish Banks Open Banking API Connector.

    Single model with bank_type selection. Bank-specific methods added
    via _inherit in separate files. Transactions flow into Odoo standard
    account.bank.statement.line records.
    """

    _name = 'bank.connector'
    _description = 'Banka Konektörü'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Bağlantı Adı', required=True, tracking=True)
    bank_type = fields.Selection(
        [
            ('garantibbva', 'Garanti BBVA'),
            ('ziraat', 'Ziraat Bankası'),
            ('qnb', 'QNB Finansbank'),
        ],
        string='Banka', required=True, tracking=True,
    )
    bank_id = fields.Many2one(
        'res.bank', string='Banka Kartı', required=True, ondelete='restrict',
    )
    company_id = fields.Many2one(
        'res.company', string='Şirket', required=True,
        default=lambda self: self.env.company,
    )

    # OAuth 2.0
    client_id = fields.Char(string='Client ID', required=True)
    client_secret = fields.Char(string='Client Secret', required=True)
    redirect_uri = fields.Char(
        string='Redirect URI',
        default='https://www.jokergrubu.com/bank/callback',
    )
    access_token = fields.Char(
        string='Access Token', copy=False, groups='base.group_system',
    )
    refresh_token = fields.Char(
        string='Refresh Token', copy=False, groups='base.group_system',
    )
    token_expires_at = fields.Datetime(
        string='Token Bitiş', copy=False, readonly=True,
    )

    # Configuration
    sandbox_mode = fields.Boolean(string='Test Modu', default=True)
    auto_sync_enabled = fields.Boolean(
        string='Otomatik Senkronizasyon', default=False,
    )
    sync_interval = fields.Integer(
        string='Senkronizasyon Aralığı (dk)', default=60,
    )

    # Status
    state = fields.Selection(
        [
            ('draft', 'Taslak'),
            ('connected', 'Bağlı'),
            ('error', 'Hata'),
            ('disconnected', 'Bağlantı Kesildi'),
        ],
        string='Durum', default='draft', required=True, tracking=True,
    )
    last_sync = fields.Datetime(string='Son Senkronizasyon', readonly=True)
    last_error = fields.Text(string='Son Hata', readonly=True)

    # Bank Accounts
    account_ids = fields.One2many(
        'res.partner.bank', 'bank_connector_id', string='Banka Hesapları',
    )
    total_accounts = fields.Integer(
        string='Hesap Sayısı', compute='_compute_statistics',
    )

    # Garanti BBVA
    garantibbva_scope = fields.Char(
        string='OAuth Scope', default='accounts payments fx',
    )

    # Ziraat
    is_corporate = fields.Boolean(string='Kurumsal Hesap', default=True)
    corporate_customer_no = fields.Char(string='Kurumsal Müşteri No')
    ziraat_tax_number = fields.Char(string='Vergi Numarası')

    # QNB
    qnb_customer_no = fields.Char(string='Müşteri No')
    qnb_branch_code = fields.Char(string='Şube Kodu')

    # -------------------------------------------------------------------------
    # Computed
    # -------------------------------------------------------------------------

    @api.depends('account_ids')
    def _compute_statistics(self):
        for rec in self:
            rec.total_accounts = len(rec.account_ids)

    # -------------------------------------------------------------------------
    # OAuth & HTTP
    # -------------------------------------------------------------------------

    def _get_base_url(self):
        self.ensure_one()
        method = getattr(self, f'_get_base_url_{self.bank_type}', None)
        if method:
            return method()
        raise UserError(_("'%s' için API URL tanımlı değil.") % self.bank_type)

    def _get_headers(self):
        self.ensure_one()
        if not self.access_token or self._is_token_expired():
            self._refresh_access_token()
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    def _is_token_expired(self):
        self.ensure_one()
        if not self.token_expires_at:
            return True
        return (
            fields.Datetime.now() + timedelta(minutes=5)
        ) >= self.token_expires_at

    def _refresh_access_token(self):
        self.ensure_one()
        method = getattr(self, f'_refresh_token_{self.bank_type}', None)
        if method:
            return method()
        raise UserError(
            _("'%s' için token yenileme tanımlı değil.") % self.bank_type
        )

    def _make_api_request(self, method, endpoint, data=None, params=None):
        self.ensure_one()
        url = f'{self._get_base_url()}{endpoint}'
        headers = self._get_headers()
        try:
            response = requests.request(
                method=method, url=url, headers=headers,
                json=data, params=params, timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            error_msg = f'HTTP {e.response.status_code}: {e.response.text[:500]}'
            _logger.error('Bank API error [%s]: %s', self.name, error_msg)
            self.write({'state': 'error', 'last_error': error_msg})
            raise UserError(error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            _logger.error('Bank API error [%s]: %s', self.name, error_msg)
            self.write({'state': 'error', 'last_error': error_msg})
            raise UserError(error_msg)

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def action_connect(self):
        self.ensure_one()
        self._refresh_access_token()
        self.write({'state': 'connected', 'last_error': False})
        return self._notify(_('Bağlantı başarılı.'), 'success')

    def action_disconnect(self):
        self.ensure_one()
        self.write({
            'state': 'disconnected',
            'access_token': False,
            'refresh_token': False,
            'token_expires_at': False,
        })
        return self._notify(_('Bağlantı kesildi.'), 'info')

    def action_test_connection(self):
        self.ensure_one()
        self._get_headers()
        return self._notify(_('Bağlantı testi başarılı.'), 'success')

    def action_view_accounts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Banka Hesapları'),
            'res_model': 'res.partner.bank',
            'view_mode': 'list,form',
            'domain': [('bank_connector_id', '=', self.id)],
        }

    # -------------------------------------------------------------------------
    # Sync Dispatch
    # -------------------------------------------------------------------------

    def sync_accounts(self):
        self.ensure_one()
        self._check_connected()
        method = getattr(self, f'_sync_accounts_{self.bank_type}', None)
        if method:
            return method()
        raise UserError(
            _("'%s' hesap senkronizasyonu desteklenmiyor.") % self.bank_type
        )

    def sync_transactions(self, date_from=None, date_to=None):
        self.ensure_one()
        self._check_connected()
        if not date_from:
            date_from = fields.Date.today() - timedelta(days=30)
        if not date_to:
            date_to = fields.Date.today()
        method = getattr(self, f'_sync_transactions_{self.bank_type}', None)
        if method:
            return method(date_from, date_to)
        raise UserError(
            _("'%s' işlem senkronizasyonu desteklenmiyor.") % self.bank_type
        )

    def sync_exchange_rates(self):
        self.ensure_one()
        self._check_connected()
        method = getattr(self, f'_sync_exchange_rates_{self.bank_type}', None)
        if method:
            return method()
        raise UserError(
            _("'%s' kur senkronizasyonu desteklenmiyor.") % self.bank_type
        )

    def action_sync_all(self):
        self.ensure_one()
        self._check_connected()
        self.sync_accounts()
        self.sync_transactions()
        self.sync_exchange_rates()
        self.last_sync = fields.Datetime.now()
        return self._notify(_('Tüm veriler senkronize edildi.'), 'success')

    @api.model
    def cron_sync_all_connectors(self):
        connectors = self.search([
            ('state', '=', 'connected'),
            ('auto_sync_enabled', '=', True),
        ])
        for connector in connectors:
            try:
                connector.sync_accounts()
                connector.sync_transactions()
                connector.last_sync = fields.Datetime.now()
                _logger.info('Auto-sync OK: %s', connector.name)
            except Exception as e:
                _logger.error('Auto-sync FAIL [%s]: %s', connector.name, e)

    # -------------------------------------------------------------------------
    # Statement Line Creation (Odoo Standard)
    # -------------------------------------------------------------------------

    def _create_statement_lines(self, bank_account, transactions_data):
        """Create account.bank.statement.line from bank API data.

        Args:
            bank_account: res.partner.bank record
            transactions_data: list of dicts with keys:
                reference, date, amount, description, partner_name,
                partner_vat, partner_iban, foreign_currency, amount_currency
        Returns:
            int: number of lines created
        """
        journal = self._get_journal_for_account(bank_account)
        if not journal:
            _logger.warning(
                'Jurnal bulunamadı: %s — Hesabı bir banka jurnali ile '
                'eşleştirin.', bank_account.acc_number,
            )
            return 0

        StatementLine = self.env['account.bank.statement.line']
        created = 0

        for tx in transactions_data:
            tx_ref = tx.get('reference')
            if not tx_ref:
                continue

            import_ref = (
                f'{self.bank_type}-'
                f'{bank_account.sanitized_acc_number}-'
                f'{tx_ref}'
            )

            if StatementLine.search_count(
                [('bank_import_ref', '=', import_ref)]
            ):
                continue

            partner_id = self._find_partner_for_transaction(tx)

            vals = {
                'journal_id': journal.id,
                'date': tx.get('date', fields.Date.today()),
                'payment_ref': tx.get('description') or tx_ref,
                'amount': float(tx.get('amount', 0)),
                'bank_import_ref': import_ref,
                'partner_id': partner_id,
                'partner_name': tx.get('partner_name', ''),
            }

            foreign_code = tx.get('foreign_currency')
            journal_currency = (
                journal.currency_id or self.env.company.currency_id
            )
            if foreign_code:
                fc = self.env['res.currency'].search(
                    [('name', '=', foreign_code.upper())], limit=1,
                )
                if fc and fc != journal_currency:
                    vals['foreign_currency_id'] = fc.id
                    vals['amount_currency'] = float(
                        tx.get('amount_currency', 0),
                    )

            try:
                StatementLine.create(vals)
                created += 1
            except Exception as e:
                _logger.error('Statement line error [%s]: %s', tx_ref, e)

        if created:
            bank_account.write({'last_sync': fields.Datetime.now()})

        return created

    def _get_journal_for_account(self, bank_account):
        return self.env['account.journal'].search([
            ('type', '=', 'bank'),
            ('bank_account_id', '=', bank_account.id),
            ('company_id', '=', self.company_id.id),
        ], limit=1)

    def _find_partner_for_transaction(self, tx_data):
        partner_vat = tx_data.get('partner_vat')
        if partner_vat:
            p = self.env['res.partner'].search(
                [('vat', '=', partner_vat)], limit=1,
            )
            if p:
                return p.id

        partner_iban = tx_data.get('partner_iban')
        if partner_iban:
            ba = self.env['res.partner.bank'].search([
                ('sanitized_acc_number', '=', partner_iban.replace(' ', '')),
            ], limit=1)
            if ba and ba.partner_id:
                return ba.partner_id.id

        partner_name = tx_data.get('partner_name')
        if partner_name and len(partner_name) > 3:
            p = self.env['res.partner'].search(
                [('name', 'ilike', partner_name)], limit=1,
            )
            if p:
                return p.id

        return False

    # -------------------------------------------------------------------------
    # Currency Rate Helper
    # -------------------------------------------------------------------------

    def _update_currency_rate(self, currency_code, rate_value, source=None):
        currency = self.env['res.currency'].search(
            [('name', '=', currency_code.upper())], limit=1,
        )
        if not currency:
            return False

        today = fields.Date.today()
        CurrencyRate = self.env['res.currency.rate']
        existing = CurrencyRate.search([
            ('currency_id', '=', currency.id),
            ('company_id', '=', self.company_id.id),
            ('name', '=', today),
        ], limit=1)

        odoo_rate = 1.0 / float(rate_value) if float(rate_value) else 0

        if existing:
            existing.write({'rate': odoo_rate})
        else:
            vals = {
                'currency_id': currency.id,
                'company_id': self.company_id.id,
                'name': today,
                'rate': odoo_rate,
            }
            if source:
                vals['source'] = source
                vals['bank_connector_id'] = self.id
            CurrencyRate.create(vals)

        return True

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _check_connected(self):
        self.ensure_one()
        if self.state != 'connected':
            raise UserError(_('Önce banka bağlantısı kurulmalı.'))

    def _notify(self, message, msg_type='info'):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': message,
                'type': msg_type,
                'sticky': False,
            },
        }

    def _get_currency_id(self, currency_code):
        if not currency_code:
            return self.env.company.currency_id.id
        currency = self.env['res.currency'].search(
            [('name', '=', currency_code.upper())], limit=1,
        )
        return currency.id if currency else self.env.company.currency_id.id
