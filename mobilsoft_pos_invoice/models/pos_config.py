from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    report_template_id = fields.Many2one(
        comodel_name="ir.actions.report",
        string="Invoice Report Template",
        domain=[("is_invoice_report", "=", True)],
        help="Select a custom invoice report template for this POS configuration. "
        "This report will be used when generating invoices for orders from this POS.",
    )
