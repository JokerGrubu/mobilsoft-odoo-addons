from odoo import fields, models


class ProductAttribute(models.Model):
    _inherit = "product.attribute"

    sync_images = fields.Boolean(
        string="Sync Images",
        default=False,
        help="If enabled, images added to a variant with this attribute will be "
        "automatically synced to all other variants with the same attribute value.\n"
        'Example: Enable for "Color" attribute to sync images across all variants '
        "with the same color.",
    )
