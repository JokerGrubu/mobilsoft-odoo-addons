from odoo import api, models


class AccountMoveSend(models.AbstractModel):
    _inherit = "account.move.send"

    @api.model
    def _get_default_pdf_report_id(self, move):
        """Override to use POS config report template if available"""
        # Check if this invoice is related to POS orders
        if move.pos_order_ids:
            # Get the first POS order's config
            pos_config = move.pos_order_ids[:1].config_id

            # If the config has a custom report template, use it
            if pos_config and pos_config.report_template_id:
                return pos_config.report_template_id

        # Otherwise, use the default behavior
        return super()._get_default_pdf_report_id(move)
