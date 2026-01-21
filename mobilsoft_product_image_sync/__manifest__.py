{
    'name': 'MobilSoft Ürün Görsel Senkronizasyonu',
    "version": "19.0.1.0.0",
    "category": "Sales",
    "summary": "Sync images across product variants with same attribute values",
    "description": """
        Product Variant Image Sync
        ==========================
        This module automatically synchronizes product images across variants
        that share the same attribute values.
        
        Features:
        ---------
        * Configure which attributes should trigger image synchronization
        * When you add an image to a product variant with specific attributes
          (e.g., Color: Red), the image is automatically added to all other
          variants that have the same attribute value
        * Works with any product attribute - you choose which ones to enable
        * Maintains unique images per attribute value combination
        * Easy to use - just enable sync for desired attributes and add images
        
        Configuration:
        --------------
        1. Go to Sales → Configuration → Attributes
        2. Open an attribute (e.g., "Color")
        3. Enable "Sync Images Across Variants" toggle
        4. Add images to any variant and watch them sync automatically!
        
        Example:
        --------
        Product: T-Shirt with variants:
        - Small/Red
        - Medium/Red
        - Large/Red
        - Small/Blue
        
        Enable sync for "Color" attribute (not "Size").
        When you add an image to "Small/Red", it will automatically be added
        to "Medium/Red" and "Large/Red" but not to "Small/Blue".
    """,
    'author': 'MobilSoft',
    'website': 'https://www.mobilsoft.net',
    "support": "destek@kitayazilim.com",
    'license': 'LGPL-3',
    "depends": [
        "product",
        "website_sale",
    ],
    "data": [
        "views/product_attribute_views.xml",
    ],
    "images": [
        "static/description/screenshot.png",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
