# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class BankSyncWizard(models.TransientModel):
    """Wizard for batch syncing bank data"""

    _name = "bank.sync.wizard"
    _description = "Bank Synchronization Wizard"

    connector_ids = fields.Many2many(
        "bank.connector.garantibbva",
        string="Connectors",
        help="Select connectors to synchronize",
    )
    sync_type = fields.Selection(
        [
            ("accounts", "Accounts Only"),
            ("transactions", "Transactions Only"),
            ("rates", "Exchange Rates Only"),
            ("all", "Everything"),
        ],
        string="Sync Type",
        default="all",
        required=True,
    )
    date_from = fields.Date(
        string="From Date",
        default=lambda self: fields.Date.today() - timedelta(days=30),
        help="Start date for transaction sync",
    )
    date_to = fields.Date(
        string="To Date",
        default=fields.Date.today,
        help="End date for transaction sync",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        # Auto-select all connected connectors
        connectors = self.env["bank.connector.garantibbva"].search(
            [("state", "=", "connected")]
        )
        res["connector_ids"] = [(6, 0, connectors.ids)]

        return res

    def action_sync(self):
        """Execute synchronization"""
        self.ensure_one()

        if not self.connector_ids:
            raise UserError(_("Please select at least one connector"))

        results = []

        for connector in self.connector_ids:
            try:
                if self.sync_type in ("accounts", "all"):
                    connector.sync_accounts()
                    results.append(f"{connector.name}: Accounts synced")

                if self.sync_type in ("transactions", "all"):
                    connector.sync_transactions(self.date_from, self.date_to)
                    results.append(f"{connector.name}: Transactions synced")

                if self.sync_type in ("rates", "all"):
                    connector.sync_exchange_rates()
                    results.append(f"{connector.name}: Exchange rates synced")

            except Exception as e:
                results.append(f"{connector.name}: ERROR - {str(e)}")

        message = "\n".join(results)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Synchronization Complete"),
                "message": message,
                "type": "success",
                "sticky": True,
            },
        }
