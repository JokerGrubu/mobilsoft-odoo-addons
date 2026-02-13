# -*- coding: utf-8 -*-

from datetime import timedelta
import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BankConnectorZiraat(models.Model):
    """Ziraat Bankası specific methods for bank.connector."""

    _inherit = 'bank.connector'

    def _get_base_url_ziraat(self):
        if self.sandbox_mode:
            return 'https://sandbox-api.ziraatbank.com.tr'
        return 'https://api.ziraatbank.com.tr'

    def _refresh_token_ziraat(self):
        import requests as req

        url = f'{self._get_base_url()}/oauth/token'
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }
        if self.is_corporate:
            data['scope'] = 'corporate_accounts corporate_payments'
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
            error_msg = f'Ziraat token hatası: {e}'
            self.write({'state': 'error', 'last_error': error_msg})
            raise UserError(error_msg)

    def _sync_accounts_ziraat(self):
        endpoint = (
            '/accounts/v1/corporate/accounts'
            if self.is_corporate
            else '/accounts/v1/accounts'
        )
        response = self._make_api_request('GET', endpoint)
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

    def _sync_transactions_ziraat(self, date_from, date_to):
        accounts = self.account_ids.filtered(
            lambda a: a.bank_external_account_id,
        )
        total = 0

        for account in accounts:
            try:
                ext_id = account.bank_external_account_id
                if self.is_corporate:
                    endpoint = (
                        f'/accounts/v1/corporate/accounts/'
                        f'{ext_id}/transactions'
                    )
                else:
                    endpoint = (
                        f'/accounts/v1/accounts/{ext_id}/transactions'
                    )

                params = {
                    'startDate': date_from.isoformat(),
                    'endDate': date_to.isoformat(),
                }
                response = self._make_api_request(
                    'GET', endpoint, params=params,
                )
                raw = response.get('transactions', [])

                transactions = []
                for tx in raw:
                    transactions.append({
                        'reference': (
                            tx.get('transactionId')
                            or tx.get('referenceNumber')
                        ),
                        'date': tx.get(
                            'valueDate',
                            tx.get('transactionDate', fields.Date.today()),
                        ),
                        'amount': float(tx.get('amount', 0)),
                        'description': tx.get('description', ''),
                        'partner_name': tx.get('counterpartyName', ''),
                        'partner_iban': tx.get('counterpartyIban', ''),
                    })

                count = self._create_statement_lines(account, transactions)
                total += count
                _logger.info(
                    'Ziraat %s: %d işlem', account.acc_number, count,
                )
            except Exception as e:
                _logger.error(
                    'Ziraat işlem hatası [%s]: %s', account.acc_number, e,
                )

        self.last_sync = fields.Datetime.now()
        return self._notify(
            _('%d işlem senkronize edildi.') % total, 'success',
        )

    def _sync_exchange_rates_ziraat(self):
        response = self._make_api_request('GET', '/fx/v1/rates')
        rates = response.get('rates', [])
        synced = 0

        for r in rates:
            code = r.get('currencyCode')
            buy = r.get('buyingRate') or r.get('buyRate')
            if not code or not buy:
                continue
            if self._update_currency_rate(code, buy, source='ziraat'):
                synced += 1

        return self._notify(_('%d kur güncellendi.') % synced, 'success')
