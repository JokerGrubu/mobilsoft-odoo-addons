# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class IrSequenceDateRange(models.Model):
    _inherit = 'ir.sequence.date_range'

    def _next(self):
        """Override to add placeholder replacement functionality"""
        result = super()._next()

        if not self.sequence_id.use_placeholder_replacement:
            return result

        month_placeholder = self.sequence_id.month_placeholder
        year_placeholder = self.sequence_id.year_placeholder

        date_value = self.date_from

        mappings = self.env['ir.sequence.mapping'].search([
            ('sequence_id', '=', self.sequence_id.id)
        ])
        if month_placeholder and month_placeholder in result:
            month_mappings = mappings.filtered(lambda m: m.mapping_type == 'month' and m.value == date_value.month)
            if month_mappings:
                replacement = month_mappings[0].get_replacement(date_value)
                if replacement:
                    result = result.replace(month_placeholder, replacement)

        if year_placeholder and year_placeholder in result:
            year_mappings = mappings.filtered(lambda m: m.mapping_type == 'year' and m.value == date_value.year)
            if year_mappings:
                replacement = year_mappings[0].get_replacement(date_value)
                if replacement:
                    result = result.replace(year_placeholder, replacement)

        return result
