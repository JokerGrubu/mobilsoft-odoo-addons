# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
import logging

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class BankConnector(models.AbstractModel):
    """Abstract base class for bank API connectors"""

    _name = "bank.connector.abstract"
    _description = "Abstract Bank Connector"
    _rec_name = "name"

    # Basic Information
    name = fields.Char(
        string="Connector Name",
        required=True,
        help="Descriptive name for this bank connection",
    )
    bank_id = fields.Many2one(
        "res.bank", string="Bank", required=True, ondelete="cascade"
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    # OAuth 2.0 Credentials
    client_id = fields.Char(
        string="Client ID",
        required=True,
        help="OAuth 2.0 Client ID provided by the bank",
    )
    client_secret = fields.Char(
        string="Client Secret",
        required=True,
        help="OAuth 2.0 Client Secret provided by the bank",
    )
    redirect_uri = fields.Char(
        string="Redirect URI",
        default="https://www.mobilsoft.net/bank/callback",
        help="OAuth 2.0 callback URL",
    )

    # Token Management
    access_token = fields.Char(string="Access Token", copy=False, readonly=True)
    refresh_token = fields.Char(string="Refresh Token", copy=False, readonly=True)
    token_expires_at = fields.Datetime(
        string="Token Expires At", copy=False, readonly=True
    )

    # Configuration
    sandbox_mode = fields.Boolean(
        string="Sandbox Mode",
        default=True,
        help="Use test/sandbox environment instead of production",
    )
    auto_sync_enabled = fields.Boolean(
        string="Auto Sync Enabled",
        default=True,
        help="Enable automatic synchronization via cron jobs",
    )
    sync_interval = fields.Integer(
        string="Sync Interval (minutes)",
        default=60,
        help="Interval for automatic synchronization in minutes",
    )

    # Status & Monitoring
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("connected", "Connected"),
            ("error", "Error"),
            ("disconnected", "Disconnected"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
    )
    last_sync = fields.Datetime(string="Last Sync", readonly=True)
    last_error = fields.Text(string="Last Error", readonly=True)

    # Statistics
    total_accounts = fields.Integer(
        string="Total Accounts", compute="_compute_statistics", store=True
    )
    total_transactions = fields.Integer(
        string="Total Transactions", compute="_compute_statistics", store=True
    )

    @api.depends("bank_id")
    def _compute_statistics(self):
        for record in self:
            if record.bank_id:
                accounts = self.env["res.partner.bank"].search_count(
                    [("bank_id", "=", record.bank_id.id)]
                )
                transactions = self.env["bank.transaction"].search_count(
                    [("bank_account_id.bank_id", "=", record.bank_id.id)]
                )
                record.total_accounts = accounts
                record.total_transactions = transactions
            else:
                record.total_accounts = 0
                record.total_transactions = 0

    @api.model
    def _get_base_url(self):
        """Get API base URL - Override in child classes"""
        raise NotImplementedError(
            _("Method _get_base_url must be implemented in child class")
        )

    def _get_headers(self):
        """Get HTTP headers for API requests"""
        self.ensure_one()

        if not self.access_token or self._is_token_expired():
            self._refresh_access_token()

        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "JOKER-CEO-Odoo19/1.0",
        }

    def _is_token_expired(self):
        """Check if access token is expired"""
        self.ensure_one()

        if not self.token_expires_at:
            return True

        # Add 5 minute buffer
        buffer_time = fields.Datetime.now() + timedelta(minutes=5)
        return buffer_time >= self.token_expires_at

    def _refresh_access_token(self):
        """Refresh OAuth access token - Override in child classes"""
        raise NotImplementedError(
            _("Method _refresh_access_token must be implemented in child class")
        )

    def _make_api_request(self, method, endpoint, data=None, params=None):
        """
        Make HTTP request to bank API

        Args:
            method (str): HTTP method (GET, POST, PUT, DELETE)
            endpoint (str): API endpoint path
            data (dict): Request body data
            params (dict): URL query parameters

        Returns:
            dict: Response JSON data
        """
        self.ensure_one()

        url = f"{self._get_base_url()}{endpoint}"
        headers = self._get_headers()

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP Error {e.response.status_code}: {e.response.text}"
            _logger.error(f"Bank API Error: {error_msg}")
            self.write({"state": "error", "last_error": error_msg})
            raise UserError(error_msg)

        except requests.exceptions.RequestException as e:
            error_msg = f"Request failed: {str(e)}"
            _logger.error(f"Bank API Request Error: {error_msg}")
            self.write({"state": "error", "last_error": error_msg})
            raise UserError(error_msg)

    def action_connect(self):
        """Initialize OAuth connection"""
        self.ensure_one()
        try:
            self._refresh_access_token()
            self.write({"state": "connected"})
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Success"),
                    "message": _("Successfully connected to bank API"),
                    "type": "success",
                    "sticky": False,
                },
            }
        except Exception as e:
            raise UserError(_("Connection failed: %s") % str(e))

    def action_disconnect(self):
        """Disconnect from bank API"""
        self.ensure_one()
        self.write(
            {
                "state": "disconnected",
                "access_token": False,
                "refresh_token": False,
                "token_expires_at": False,
            }
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Disconnected"),
                "message": _("Successfully disconnected from bank API"),
                "type": "info",
                "sticky": False,
            },
        }

    def action_test_connection(self):
        """Test API connection"""
        self.ensure_one()
        try:
            self._get_headers()  # This will refresh token if needed
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Success"),
                    "message": _("Connection test successful"),
                    "type": "success",
                    "sticky": False,
                },
            }
        except Exception as e:
            raise UserError(_("Connection test failed: %s") % str(e))

    def sync_accounts(self):
        """Fetch and sync bank accounts - Override in child classes"""
        raise NotImplementedError(
            _("Method sync_accounts must be implemented in child class")
        )

    def sync_transactions(self, date_from=None, date_to=None):
        """Fetch and sync transactions - Override in child classes"""
        raise NotImplementedError(
            _("Method sync_transactions must be implemented in child class")
        )

    def sync_exchange_rates(self):
        """Fetch and sync currency exchange rates - Override in child classes"""
        raise NotImplementedError(
            _("Method sync_exchange_rates must be implemented in child class")
        )

    def action_sync_all(self):
        """Sync all data (accounts, transactions, rates)"""
        self.ensure_one()

        if self.state != "connected":
            raise UserError(_("Connector must be connected before syncing"))

        try:
            self.sync_accounts()
            self.sync_transactions()
            self.sync_exchange_rates()

            self.last_sync = fields.Datetime.now()

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Success"),
                    "message": _("All data synchronized successfully"),
                    "type": "success",
                    "sticky": False,
                },
            }
        except Exception as e:
            raise UserError(_("Sync failed: %s") % str(e))

    @api.model
    def cron_sync_all_connectors(self):
        """Cron job to sync all active connectors"""
        connectors = self.search(
            [("state", "=", "connected"), ("auto_sync_enabled", "=", True)]
        )

        for connector in connectors:
            try:
                connector.sync_transactions()
                _logger.info(f"Auto-sync successful for {connector.name}")
            except Exception as e:
                _logger.error(f"Auto-sync failed for {connector.name}: {str(e)}")

    def _get_currency_id(self, currency_code):
        """Get currency ID from currency code"""
        if not currency_code:
            return self.env.company.currency_id.id

        currency = self.env["res.currency"].search(
            [("name", "=", currency_code.upper())], limit=1
        )

        if not currency:
            _logger.warning(
                f"Currency {currency_code} not found, using company currency"
            )
            return self.env.company.currency_id.id

        return currency.id
