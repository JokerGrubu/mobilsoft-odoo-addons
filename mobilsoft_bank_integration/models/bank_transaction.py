# -*- coding: utf-8 -*-

import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class BankTransaction(models.Model):
    """Bank transaction records from API sync"""

    _name = "bank.transaction"
    _description = "Bank Transaction"
    _order = "date desc, id desc"
    _rec_name = "reference"

    # Basic Information
    reference = fields.Char(
        string="Reference",
        required=True,
        index=True,
        help="Unique transaction reference from bank",
    )
    bank_account_id = fields.Many2one(
        "res.partner.bank",
        string="Bank Account",
        required=True,
        ondelete="cascade",
        index=True,
    )
    date = fields.Date(string="Date", required=True, index=True)

    # Transaction Details
    amount = fields.Monetary(
        string="Amount", required=True, currency_field="currency_id"
    )
    currency_id = fields.Many2one("res.currency", string="Currency", required=True)
    transaction_type = fields.Selection(
        [
            ("debit", "Debit"),
            ("credit", "Credit"),
        ],
        string="Type",
        compute="_compute_transaction_type",
        store=True,
    )

    # Counterparty Information
    partner_name = fields.Char(string="Counterparty Name")
    partner_id = fields.Many2one(
        "res.partner", string="Partner", help="Matched partner from Odoo"
    )

    # Description & Notes
    description = fields.Text(string="Description")
    notes = fields.Text(string="Internal Notes")

    # Balance Information
    balance_after = fields.Monetary(
        string="Balance After",
        currency_field="currency_id",
        help="Account balance after this transaction",
    )

    # Reconciliation
    state = fields.Selection(
        [
            ("unreconciled", "Unreconciled"),
            ("matched", "Matched"),
            ("reconciled", "Reconciled"),
        ],
        string="Status",
        default="unreconciled",
        required=True,
        tracking=True,
    )
    statement_line_id = fields.Many2one(
        "account.bank.statement.line",
        string="Statement Line",
        help="Linked bank statement line",
    )

    # Related Fields
    company_id = fields.Many2one(
        related="bank_account_id.company_id", string="Company", store=True
    )
    bank_id = fields.Many2one(
        related="bank_account_id.bank_id", string="Bank", store=True
    )

    _sql_constraints = [
        (
            "unique_reference_account",
            "UNIQUE(reference, bank_account_id)",
            "Transaction reference must be unique per bank account!",
        )
    ]

    @api.depends("amount")
    def _compute_transaction_type(self):
        for record in self:
            if record.amount >= 0:
                record.transaction_type = "credit"
            else:
                record.transaction_type = "debit"

    def action_match_partner(self):
        """Try to match transaction with existing partner"""
        self.ensure_one()

        if not self.partner_name:
            return

        # Search for partner by name
        partner = self.env["res.partner"].search(
            [
                "|",
                ("name", "ilike", self.partner_name),
                ("vat", "ilike", self.partner_name),
            ],
            limit=1,
        )

        if partner:
            self.partner_id = partner
            self.state = "matched"

    def action_create_statement_line(self):
        """Create bank statement line from this transaction"""
        self.ensure_one()

        # Find or create bank statement for this date
        statement = self.env["account.bank.statement"].search(
            [
                ("journal_id.bank_account_id", "=", self.bank_account_id.id),
                ("date", "=", self.date),
            ],
            limit=1,
        )

        if not statement:
            # Create new statement
            journal = self.env["account.journal"].search(
                [
                    ("bank_account_id", "=", self.bank_account_id.id),
                    ("type", "=", "bank"),
                ],
                limit=1,
            )

            if not journal:
                from odoo.exceptions import UserError

                raise UserError(_("No bank journal found for this account"))

            statement = self.env["account.bank.statement"].create(
                {
                    "journal_id": journal.id,
                    "date": self.date,
                    "name": f"Bank Statement {self.date}",
                }
            )

        # Create statement line
        line_vals = {
            "statement_id": statement.id,
            "date": self.date,
            "payment_ref": self.description or self.reference,
            "ref": self.reference,
            "partner_id": self.partner_id.id if self.partner_id else False,
            "amount": self.amount,
        }

        line = self.env["account.bank.statement.line"].create(line_vals)

        self.write({"statement_line_id": line.id, "state": "reconciled"})

        return {
            "type": "ir.actions.act_window",
            "res_model": "account.bank.statement.line",
            "res_id": line.id,
            "view_mode": "form",
            "target": "current",
        }
