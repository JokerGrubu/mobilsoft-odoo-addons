# -*- coding: utf-8 -*-
from odoo import models, fields


class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    use_placeholder_replacement = fields.Boolean(
        string='Use Placeholder Replacement',
        default=False,
        help='Enable dynamic placeholder replacement in this sequence'
    )
    month_placeholder = fields.Char(
        string='Month Placeholder',
        default='@',
        size=10,
        help='Character(s) that will be replaced with the month representation'
    )
    year_placeholder = fields.Char(
        string='Year Placeholder',
        default='#',
        size=10,
        help='Character(s) that will be replaced with the year representation'
    )
    mapping_ids = fields.One2many(
        'ir.sequence.mapping',
        'sequence_id',
        string='Placeholder Mappings'
    )