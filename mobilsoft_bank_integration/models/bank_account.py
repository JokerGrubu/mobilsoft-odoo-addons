# -*- coding: utf-8 -*-

from odoo import fields, models


class ResPartnerBank(models.Model):
    """Extend partner bank account with integration fields"""

    _inherit = "res.partner.bank"

    # Integration tracking
    last_sync = fields.Datetime(
        string="Last Sync",
        readonly=True,
        help="Last time transactions were synced for this account",
    )
    transaction_count = fields.Integer(
        string="Transactions", compute="_compute_transaction_count"
    )

    def _compute_transaction_count(self):
        for record in self:
            record.transaction_count = self.env["bank.transaction"].search_count(
                [("bank_account_id", "=", record.id)]
            )

    def action_view_transactions(self):
        """View transactions for this account"""
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Bank Transactions",
            "res_model": "bank.transaction",
            "view_mode": "list,form",
            "domain": [("bank_account_id", "=", self.id)],
            "context": {"default_bank_account_id": self.id},
        }
