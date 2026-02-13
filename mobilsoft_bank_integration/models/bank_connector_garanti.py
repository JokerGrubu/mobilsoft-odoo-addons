# -*- coding: utf-8 -*-

from datetime import timedelta
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BankConnectorGaranti(models.Model):
    """Garanti BBVA specific methods for bank.connector."""

    _inherit = 'bank.connector'

    def _get_base_url_garantibbva(self):
        if self.sandbox_mode:
            return 'https://sandbox.api.garantibbva.com.tr'
        return 'https://api.garantibbva.com.tr'

    def _refresh_token_garantibbva(self):
        import requests as req

        url = f'{self._get_base_url()}/oauth2/token'
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scope': self.garantibbva_scope or 'accounts payments fx',
        }
        try:
            resp = req.post(url, data=data, timeout=30)
            resp.raise_for_status()
            result = resp.json()
            self.write({
                'access_token': result['access_token'],
                'refresh_token': result.get('refresh_token'),
                'token_expires_at': (
                    fields.Datetime.now()
                    + timedelta(seconds=result.get('expires_in', 3600))
                ),
                'state': 'connected',
                'last_error': False,
            })
        except Exception as e:
            error_msg = f'Garanti token hatası: {e}'
            self.write({'state': 'error', 'last_error': error_msg})
            raise UserError(error_msg)

    def _sync_accounts_garantibbva(self):
        response = self._make_api_request('GET', '/v1/accounts')
        accounts_data = response.get('accounts', [])
        BankAccount = self.env['res.partner.bank']
        synced = 0

        for acc in accounts_data:
            acc_number = acc.get('accountNumber')
            if not acc_number:
                continue

            existing = BankAccount.search([
                ('bank_id', '=', self.bank_id.id),
                ('acc_number', '=', acc_number),
            ], limit=1)

            vals = {
                'bank_id': self.bank_id.id,
                'partner_id': self.company_id.partner_id.id,
                'acc_number': acc_number,
                'acc_holder_name': acc.get(
                    'accountName', self.company_id.name,
                ),
                'currency_id': self._get_currency_id(
                    acc.get('currency', 'TRY'),
                ),
                'bank_connector_id': self.id,
                'bank_external_account_id': acc.get('accountId'),
            }

            if existing:
                existing.write(vals)
            else:
                BankAccount.create(vals)
            synced += 1

        self.last_sync = fields.Datetime.now()
        return self._notify(_('%d hesap senkronize edildi.') % synced, 'success')

    def _sync_transactions_garantibbva(self, date_from, date_to):
        accounts = self.account_ids.filtered(
            lambda a: a.bank_external_account_id,
        )
        total = 0

        for account in accounts:
            try:
                endpoint = (
                    f'/v1/accounts/'
                    f'{account.bank_external_account_id}/transactions'
                )
                params = {
                    'fromDate': date_from.isoformat(),
                    'toDate': date_to.isoformat(),
                }
                response = self._make_api_request(
                    'GET', endpoint, params=params,
                )
                raw = response.get('transactions', [])

                transactions = []
                for tx in raw:
                    transactions.append({
                        'reference': tx.get('transactionId'),
                        'date': tx.get('valueDate', fields.Date.today()),
                        'amount': float(tx.get('amount', 0)),
                        'description': tx.get('description', ''),
                        'partner_name': tx.get('counterpartyName', ''),
                        'partner_iban': tx.get('counterpartyIban', ''),
                    })

                count = self._create_statement_lines(account, transactions)
                total += count
                _logger.info(
                    'Garanti %s: %d işlem', account.acc_number, count,
                )
            except Exception as e:
                _logger.error(
                    'Garanti işlem hatası [%s]: %s', account.acc_number, e,
                )

        self.last_sync = fields.Datetime.now()
        return self._notify(
            _('%d işlem senkronize edildi.') % total, 'success',
        )

    def _sync_exchange_rates_garantibbva(self):
        response = self._make_api_request('GET', '/v1/fx/rates')
        rates = response.get('rates', [])
        synced = 0

        for r in rates:
            code = r.get('currency')
            buy = r.get('buyRate')
            if not code or not buy:
                continue
            if self._update_currency_rate(code, buy, source='garantibbva'):
                synced += 1

        return self._notify(_('%d kur güncellendi.') % synced, 'success')
