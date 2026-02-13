# -*- coding: utf-8 -*-

from odoo import fields, models


class AccountBankStatementLine(models.Model):
    """Extend statement line with bank import reference for deduplication."""

    _inherit = 'account.bank.statement.line'

    bank_import_ref = fields.Char(
        string='Banka Import Referansı',
        index=True,
        copy=False,
        help='Mükerrer önleme için benzersiz banka işlem referansı',
    )

    _sql_constraints = [
        (
            'unique_bank_import_ref',
            'UNIQUE(bank_import_ref)',
            'Bu banka işlemi zaten içeri aktarılmış!',
        ),
    ]
