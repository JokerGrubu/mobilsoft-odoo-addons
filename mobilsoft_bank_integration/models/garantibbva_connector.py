# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class GarantiBBVAConnector(models.Model):
    """Garanti BBVA Open Banking API Connector"""

    _name = "bank.connector.garantibbva"
    _inherit = "bank.connector.abstract"
    _description = "Garanti BBVA Bank Connector"

    # Garanti BBVA Specific Fields
    garantibbva_scope = fields.Char(
        string="OAuth Scope",
        default="accounts payments fx",
        help="OAuth 2.0 scopes for API access",
    )

    @api.model
    def _get_base_url(self):
        """Get Garanti BBVA API base URL"""
        if self.sandbox_mode:
            return "https://sandbox.api.garantibbva.com.tr"
        return "https://api.garantibbva.com.tr"

    def _refresh_access_token(self):
        """Get OAuth 2.0 access token from Garanti BBVA"""
        self.ensure_one()

        url = f"{self._get_base_url()}/oauth2/token"

        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": self.garantibbva_scope,
        }

        try:
            import requests

            response = requests.post(url, data=data, timeout=30)
            response.raise_for_status()
            result = response.json()

            expires_in = result.get("expires_in", 3600)

            self.write(
                {
                    "access_token": result["access_token"],
                    "refresh_token": result.get("refresh_token"),
                    "token_expires_at": fields.Datetime.now()
                    + timedelta(seconds=expires_in),
                    "state": "connected",
                    "last_error": False,
                }
            )

            _logger.info(f"Garanti BBVA token refreshed successfully for {self.name}")

        except Exception as e:
            error_msg = f"Token refresh failed: {str(e)}"
            _logger.error(f"Garanti BBVA OAuth Error: {error_msg}")
            self.write({"state": "error", "last_error": error_msg})
            raise UserError(error_msg)

    def sync_accounts(self):
        """Fetch and sync Garanti BBVA accounts"""
        self.ensure_one()

        _logger.info(f"Starting account sync for {self.name}")

        try:
            response_data = self._make_api_request("GET", "/v1/accounts")
            accounts_data = response_data.get("accounts", [])

            BankAccount = self.env["res.partner.bank"]
            synced_count = 0

            for acc_data in accounts_data:
                account_number = acc_data.get("accountNumber")
                account_id = acc_data.get("accountId")

                if not account_number:
                    continue

                # Search for existing account
                account = BankAccount.search(
                    [
                        ("bank_id", "=", self.bank_id.id),
                        ("acc_number", "=", account_number),
                    ],
                    limit=1,
                )

                currency_code = acc_data.get("currency", "TRY")

                vals = {
                    "bank_id": self.bank_id.id,
                    "partner_id": self.company_id.partner_id.id,
                    "acc_number": account_number,
                    "acc_holder_name": acc_data.get(
                        "accountName", self.company_id.name
                    ),
                    "currency_id": self._get_currency_id(currency_code),
                    "garantibbva_account_id": account_id,
                    "garantibbva_account_type": acc_data.get("accountType"),
                    "garantibbva_iban": acc_data.get("iban"),
                }

                if account:
                    account.write(vals)
                    _logger.debug(f"Updated account: {account_number}")
                else:
                    account = BankAccount.create(vals)
                    _logger.debug(f"Created account: {account_number}")

                synced_count += 1

            self.last_sync = fields.Datetime.now()
            _logger.info(f"Account sync completed: {synced_count} accounts")

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Success"),
                    "message": _("%d accounts synchronized") % synced_count,
                    "type": "success",
                },
            }

        except Exception as e:
            error_msg = f"Account sync failed: {str(e)}"
            _logger.error(error_msg)
            raise UserError(error_msg)

    def sync_transactions(self, date_from=None, date_to=None):
        """Fetch and sync transactions for all Garanti BBVA accounts"""
        self.ensure_one()

        if not date_from:
            date_from = fields.Date.today() - timedelta(days=30)
        if not date_to:
            date_to = fields.Date.today()

        _logger.info(f"Starting transaction sync from {date_from} to {date_to}")

        BankAccount = self.env["res.partner.bank"]
        accounts = BankAccount.search(
            [("bank_id", "=", self.bank_id.id), ("garantibbva_account_id", "!=", False)]
        )

        total_transactions = 0

        for account in accounts:
            try:
                endpoint = f"/v1/accounts/{account.garantibbva_account_id}/transactions"
                params = {
                    "fromDate": date_from.isoformat(),
                    "toDate": date_to.isoformat(),
                }

                response_data = self._make_api_request("GET", endpoint, params=params)
                transactions_data = response_data.get("transactions", [])

                count = self._create_transactions(account, transactions_data)
                total_transactions += count

                _logger.info(
                    f"Synced {count} transactions for account {account.acc_number}"
                )

            except Exception as e:
                _logger.error(
                    f"Transaction sync failed for {account.acc_number}: {str(e)}"
                )
                continue

        self.last_sync = fields.Datetime.now()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Success"),
                "message": _("%d transactions synchronized") % total_transactions,
                "type": "success",
            },
        }

    def sync_exchange_rates(self):
        """Fetch and update currency exchange rates from Garanti BBVA"""
        self.ensure_one()

        _logger.info("Starting exchange rate sync")

        try:
            response_data = self._make_api_request("GET", "/v1/fx/rates")
            rates_data = response_data.get("rates", [])

            CurrencyRate = self.env["res.currency.rate"]
            synced_count = 0
            today = fields.Date.today()

            for rate_info in rates_data:
                currency_code = rate_info.get("currency")
                buy_rate = rate_info.get("buyRate")

                if not currency_code or not buy_rate:
                    continue

                currency = self.env["res.currency"].search(
                    [("name", "=", currency_code.upper())], limit=1
                )

                if not currency:
                    _logger.warning(f"Currency {currency_code} not found in system")
                    continue

                # Check if rate already exists for today
                existing_rate = CurrencyRate.search(
                    [
                        ("currency_id", "=", currency.id),
                        ("company_id", "=", self.company_id.id),
                        ("name", "=", today),
                    ],
                    limit=1,
                )

                # Odoo stores inverse rate (1 foreign = X base)
                rate_value = 1.0 / float(buy_rate)

                vals = {
                    "currency_id": currency.id,
                    "company_id": self.company_id.id,
                    "rate": rate_value,
                    "name": today,
                    "source": "garantibbva",
                    "bank_connector_id": self.id,
                }

                if existing_rate:
                    existing_rate.write({"rate": rate_value})
                else:
                    CurrencyRate.create(vals)

                synced_count += 1
                _logger.debug(f"Updated rate for {currency_code}: {rate_value}")

            _logger.info(f"Exchange rate sync completed: {synced_count} rates")

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Success"),
                    "message": _("%d exchange rates synchronized") % synced_count,
                    "type": "success",
                },
            }

        except Exception as e:
            error_msg = f"Exchange rate sync failed: {str(e)}"
            _logger.error(error_msg)
            raise UserError(error_msg)

    def _create_transactions(self, account, transactions_data):
        """Create bank transaction records"""
        BankTransaction = self.env["bank.transaction"]
        created_count = 0

        for trans_data in transactions_data:
            transaction_id = trans_data.get("transactionId")

            if not transaction_id:
                continue

            # Check if transaction already exists
            existing = BankTransaction.search(
                [
                    ("bank_account_id", "=", account.id),
                    ("reference", "=", transaction_id),
                ],
                limit=1,
            )

            if existing:
                continue

            # Parse transaction date
            value_date = trans_data.get("valueDate")
            if isinstance(value_date, str):
                value_date = fields.Date.from_string(value_date)

            vals = {
                "bank_account_id": account.id,
                "reference": transaction_id,
                "date": value_date or fields.Date.today(),
                "amount": float(trans_data.get("amount", 0)),
                "currency_id": account.currency_id.id,
                "partner_name": trans_data.get("counterpartyName"),
                "description": trans_data.get("description"),
                "transaction_type": trans_data.get("type"),
                "balance_after": float(trans_data.get("balanceAfter", 0)),
            }

            BankTransaction.create(vals)
            created_count += 1

        return created_count


class ResPartnerBank(models.Model):
    """Extend bank account with Garanti BBVA specific fields"""

    _inherit = "res.partner.bank"

    garantibbva_account_id = fields.Char(
        string="Garanti BBVA Account ID",
        help="Unique account identifier from Garanti BBVA API",
    )
    garantibbva_account_type = fields.Char(
        string="Account Type",
        help="Account type from Garanti BBVA (e.g., CURRENT, SAVINGS)",
    )
    garantibbva_iban = fields.Char(
        string="IBAN", help="International Bank Account Number"
    )
