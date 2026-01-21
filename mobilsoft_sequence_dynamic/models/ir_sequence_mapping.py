# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class IrSequenceMapping(models.Model):
    _name = 'ir.sequence.mapping'
    _description = 'Sequence Placeholder Mapping'
    _order = 'sequence_id, mapping_type, value'

    sequence_id = fields.Many2one(
        'ir.sequence',
        string='Sequence',
        required=True,
        ondelete='cascade'
    )
    mapping_type = fields.Selection([
        ('month', 'Month'),
        ('year', 'Year')
    ], string='Mapping Type', required=True)
    value = fields.Integer(
        string='Value',
        required=True,
        help='The numeric value to map (e.g., 1-12 for months, year number for years)'
    )
    replacement = fields.Char(
        string='Replacement',
        required=True,
        help='The character or value that will replace the placeholder'
    )

    def get_replacement(self, date_value):
        """
        Get the replacement value for the given date value based on the mapping type.

        :param date_value: datetime object
        :return: replacement string
        """
        self.ensure_one()

        if self.mapping_type == 'month':
            value = date_value.month
        elif self.mapping_type == 'year':
            value = date_value.year
        else:
            return ''

        if self.value != value:
            return None

        return self.replacement
