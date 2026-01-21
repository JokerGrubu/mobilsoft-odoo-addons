from odoo import models


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _get_variant_attribute_values_dict(self):
        """Get attribute values as a dictionary for comparison"""
        self.ensure_one()
        return {
            attr_value.attribute_id.id: attr_value.id
            for attr_value in self.product_template_attribute_value_ids.product_attribute_value_id
        }

    def _get_sync_enabled_attribute_ids(self):
        """Get IDs of attributes that have image sync enabled"""
        self.ensure_one()
        sync_attributes = self.product_template_attribute_value_ids.filtered(
            lambda v: v.attribute_id.sync_images
        ).mapped("attribute_id")
        return sync_attributes.ids

    def _find_variants_with_same_attributes(self, attribute_ids):
        """
        Find all variants that share the same attribute values
        for the given attribute IDs (only for attributes with sync_images enabled)
        """
        self.ensure_one()

        if not attribute_ids:
            return self.env["product.product"]

        # Get the attribute values for this variant
        my_values = self.product_template_attribute_value_ids.filtered(
            lambda v: v.attribute_id.id in attribute_ids
        ).product_attribute_value_id

        if not my_values:
            return self.env["product.product"]

        # Find all variants from the same template that have the same attribute values
        all_variants = self.product_tmpl_id.product_variant_ids
        matching_variants = self.env["product.product"]

        for variant in all_variants:
            if variant.id == self.id:
                continue

            variant_values = variant.product_template_attribute_value_ids.filtered(
                lambda v: v.attribute_id.id in attribute_ids
            ).product_attribute_value_id

            # Check if all specified attribute values match
            if my_values == variant_values:
                matching_variants |= variant

        return matching_variants
