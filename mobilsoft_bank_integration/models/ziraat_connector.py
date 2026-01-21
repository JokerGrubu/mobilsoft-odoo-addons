# -*- coding: utf-8 -*-

from datetime import timedelta
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ZiraatConnector(models.Model):
    """Ziraat Bank Open Banking API Connector"""

    _name = "bank.connector.ziraat"
    _inherit = "bank.connector.abstract"
    _description = "Ziraat Bank Connector"

    # Ziraat Specific Fields
    is_corporate = fields.Boolean(
        string="Corporate Account",
        default=True,
        help="Enable corporate account features",
    )
    corporate_customer_no = fields.Char(
        string="Corporate Customer No",
        help="Corporate customer number for business accounts",
    )
    tax_number = fields.Char(
        string="Tax Number", help="Company tax number for corporate accounts"
    )

    @api.model
    def _get_base_url(self):
        """Get Ziraat Bank API base URL"""
        if self.sandbox_mode:
            return "https://sandbox-api.ziraatbank.com.tr"
        return "https://api.ziraatbank.com.tr"

    def _refresh_access_token(self):
        """Get OAuth 2.0 access token from Ziraat Bank"""
        self.ensure_one()

        url = f"{self._get_base_url()}/oauth/token"

        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        # Add corporate-specific parameters if needed
        if self.is_corporate:
            data["scope"] = "corporate_accounts corporate_payments"

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

            _logger.info(f"Ziraat Bank token refreshed successfully for {self.name}")

        except Exception as e:
            error_msg = f"Token refresh failed: {str(e)}"
            _logger.error(f"Ziraat OAuth Error: {error_msg}")
            self.write({"state": "error", "last_error": error_msg})
            raise UserError(error_msg)

    def sync_accounts(self):
        """Fetch and sync Ziraat Bank accounts"""
        self.ensure_one()

        _logger.info(f"Starting account sync for {self.name}")

        try:
            endpoint = "/accounts/v1/accounts"
            if self.is_corporate:
                endpoint = "/accounts/v1/corporate/accounts"

            response_data = self._make_api_request("GET", endpoint)
            accounts_data = response_data.get("accounts", [])

            BankAccount = self.env["res.partner.bank"]
            synced_count = 0

            for acc_data in accounts_data:
                account_number = acc_data.get("accountNumber")

                if not account_number:
                    continue

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
                    "ziraat_account_id": acc_data.get("accountId"),
                    "ziraat_iban": acc_data.get("iban"),
                }

                if account:
                    account.write(vals)
                else:
                    BankAccount.create(vals)

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
        """Fetch and sync transactions for all Ziraat Bank accounts"""
        self.ensure_one()

        if not date_from:
            date_from = fields.Date.today() - timedelta(days=30)
        if not date_to:
            date_to = fields.Date.today()

        _logger.info(f"Starting transaction sync from {date_from} to {date_to}")

        # Implementation similar to Garanti BBVA
        # This is a placeholder for actual API integration

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Info"),
                "message": _("Ziraat transaction sync - Implementation pending"),
                "type": "info",
            },
        }

    def sync_exchange_rates(self):
        """Fetch and update currency exchange rates from Ziraat Bank"""
        self.ensure_one()

        _logger.info("Starting exchange rate sync for Ziraat")

        # Implementation placeholder
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Info"),
                "message": _("Ziraat exchange rate sync - Implementation pending"),
                "type": "info",
            },
        }


class ResPartnerBankZiraat(models.Model):
    """Extend bank account with Ziraat specific fields"""

    _inherit = "res.partner.bank"

    ziraat_account_id = fields.Char(
        string="Ziraat Account ID",
        help="Unique account identifier from Ziraat Bank API",
    )
    ziraat_iban = fields.Char(string="IBAN", help="International Bank Account Number")
