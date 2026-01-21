from odoo import models, api


class ProductImage(models.Model):
    _inherit = "product.image"

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to sync images to variants with same attributes"""

        # Skip sync if we're already in a sync operation (prevent recursion)
        if not self.env.context.get("skip_image_sync"):
            # Filter out duplicate images before creation
            filtered_vals_list = []
            for vals in vals_list:
                if vals.get("product_variant_id") and vals.get("image_1920"):
                    # Check if same image already exists for this variant
                    existing = self.search(
                        [
                            ("product_variant_id", "=", vals["product_variant_id"]),
                            ("name", "=", vals["name"]),
                        ],
                        limit=1,
                    )

                    if existing:
                        # Same image already exists, skip this one
                        continue

                filtered_vals_list.append(vals)

            # If all were duplicates, return empty recordset
            if not filtered_vals_list:
                return self.env["product.image"]

            vals_list = filtered_vals_list

        images = super().create(vals_list)

        # Skip sync if we're already in a sync operation (prevent recursion)
        if self.env.context.get("skip_image_sync"):
            return images

        # Process each created image
        for image in images:
            if image.product_variant_id:
                variant = image.product_variant_id

                # Check if variant has a main image (cover image)
                variant_has_cover = bool(variant.image_variant_1920)

                if not variant_has_cover and image.image_1920:
                    # No cover image exists, set this as cover and delete product.image record
                    variant.with_context(skip_image_sync=True).write(
                        {
                            "image_variant_1920": image.image_1920,
                        }
                    )
                    # Store image data before deleting for sync
                    image_data = {
                        "name": image.name,
                        "image_1920": image.image_1920,
                        "video_url": image.video_url,
                        "sequence": image.sequence,
                    }
                    # Delete this product.image record
                    image.with_context(skip_image_sync=True).unlink()
                    # Sync to matching variants with the stored data
                    self._sync_cover_image_to_matching_variants(variant, image_data)
                else:
                    # Cover image exists, keep as normal product.image
                    self._sync_image_to_matching_variants(image)

        return images

    def write(self, vals):
        """Override write to sync image changes"""
        result = super().write(vals)

        # Skip sync if we're already in a sync operation (prevent recursion)
        if self.env.context.get("skip_image_sync"):
            return result

        # If image or video_url is updated, sync to matching variants
        if "image_1920" in vals or "video_url" in vals:
            for image in self:
                if image.product_variant_id:
                    self._sync_image_to_matching_variants(image)

        return result

    def _sync_image_to_matching_variants(self, image):
        """
        Sync the image to all variants that share the same attribute values
        (only for attributes with sync_images flag enabled)
        """
        if not image.product_variant_id:
            return

        variant = image.product_variant_id

        # Get only the attribute IDs that have sync_images enabled
        sync_attribute_ids = variant._get_sync_enabled_attribute_ids()

        if not sync_attribute_ids:
            # No attributes have sync enabled, skip synchronization
            return

        # Find variants with matching attributes (only for sync-enabled attributes)
        matching_variants = variant._find_variants_with_same_attributes(
            sync_attribute_ids
        )

        if not matching_variants:
            return

        # For each matching variant, sync the image
        for matching_variant in matching_variants:
            # Check if target variant has any images at all
            target_variant_has_image = bool(matching_variant.image_variant_1920)

            # If target doesn't have a main image, set as cover image only
            if not target_variant_has_image:
                # Set as main variant image only (no product.image record)
                matching_variant.with_context(skip_image_sync=True).write(
                    {
                        "image_variant_1920": image.image_1920,
                    }
                )
            else:
                # Target has a main image, add as additional product.image
                # First check if the same image already exists (by image content)
                existing_image = self.search(
                    [
                        ("product_variant_id", "=", matching_variant.id),
                        ("name", "=", image.name),
                    ],
                    limit=1,
                )

                if existing_image:
                    # Same image already exists, skip
                    continue

                # Check if image with same name exists
                existing_image_by_name = self.search(
                    [
                        ("product_variant_id", "=", matching_variant.id),
                        ("name", "=", image.name),
                    ],
                    limit=1,
                )

                if not existing_image_by_name:
                    # Create a copy of the image for this variant
                    # Use context flag to prevent infinite recursion
                    self.with_context(skip_image_sync=True).create(
                        {
                            "name": image.name,
                            "image_1920": image.image_1920,
                            "video_url": image.video_url,
                            "product_variant_id": matching_variant.id,
                            "sequence": image.sequence,
                        }
                    )
                else:
                    # Update existing image with same name
                    # Use context flag to prevent infinite recursion
                    existing_image_by_name.with_context(skip_image_sync=True).write(
                        {
                            "image_1920": image.image_1920,
                            "video_url": image.video_url,
                            "sequence": image.sequence,
                        }
                    )

    def _sync_cover_image_to_matching_variants(self, variant, image_data):
        """
        Sync cover image to matching variants (used when source has no cover)
        """
        # Get only the attribute IDs that have sync_images enabled
        sync_attribute_ids = variant._get_sync_enabled_attribute_ids()

        if not sync_attribute_ids:
            return

        # Find variants with matching attributes
        matching_variants = variant._find_variants_with_same_attributes(
            sync_attribute_ids
        )

        if not matching_variants:
            return

        # For each matching variant, set as cover if they don't have one
        for matching_variant in matching_variants:
            # Check if variant already has this exact image as cover
            if matching_variant.image_variant_1920 == image_data["image_1920"]:
                # Same image already exists as cover, skip
                continue

            if not matching_variant.image_variant_1920:
                matching_variant.with_context(skip_image_sync=True).write(
                    {
                        "image_variant_1920": image_data["image_1920"],
                    }
                )
