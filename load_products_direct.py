#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Joker Grubu ürünlerini direkt Odoo ORM ile yükle.
Odoo container içinde çalıştırılacak: docker exec -it joker-odoo python3 /mnt/extra-addons/load_products_direct.py
"""

import csv
import json
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# CSV dosya yolları (container içinden erişilebilir)
TEMPLATES_CSV = '/Mimar/sirket_verileri/JokerGrubu_Mevcut_Veriler/product_templates_joker.csv'
VARIANTS_CSV = '/Mimar/sirket_verileri/JokerGrubu_Mevcut_Veriler/import_product_variants.csv'

def load_odoo_env():
    """Odoo environment'ı yükle"""
    import odoo
    from odoo import api, SUPERUSER_ID

    db_name = 'Joker'

    # Odoo registry'yi yükle
    registry = odoo.registry(db_name)

    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        return env, cr

def get_or_create_category(env, category_path):
    """Kategori bul veya oluştur"""
    if not category_path or category_path == 'Mobil Cihaz Aksesuarları':
        # Ana kategoriyi bul
        cat = env['product.category'].search([('name', '=', 'Mobil Cihaz Aksesuarları')], limit=1)
        return cat.id if cat else 1

    # Alt kategoriler (örn: "Mobil Cihaz Aksesuarları / HAFIZA")
    parts = category_path.split(' / ')
    parent_id = False

    for part in parts:
        cat = env['product.category'].search([
            ('name', '=', part.strip()),
            ('parent_id', '=', parent_id)
        ], limit=1)

        if cat:
            parent_id = cat.id
        else:
            # Oluştur
            parent_id = env['product.category'].create({
                'name': part.strip(),
                'parent_id': parent_id or False
            }).id

    return parent_id

def import_templates(env, cr):
    """Ürün şablonlarını yükle"""
    logger.info("\n" + "="*60)
    logger.info("📦 ÜRÜN ŞABLONLARI YÜKLEME BAŞLIYOR...")
    logger.info("="*60)

    created = 0
    skipped = 0
    errors = []

    ProductTemplate = env['product.template']

    with open(TEMPLATES_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for i, row in enumerate(reader, 1):
            try:
                name = row.get('name', '').strip()
                default_code = row.get('default_code', '').strip() or False
                barcode = row.get('barcode', '').strip() or False
                list_price = row.get('list_price', '').strip()
                standard_price = row.get('standard_price', '').strip()
                category_path = row.get('categ_id', 'Mobil Cihaz Aksesuarları').strip()

                if not name:
                    skipped += 1
                    continue

                # Kategori ID
                categ_id = get_or_create_category(env, category_path)

                # Ürün verisi
                vals = {
                    'name': name,
                    'categ_id': categ_id,
                    'list_price': float(list_price) if list_price else 0.0,
                    'standard_price': float(standard_price) if standard_price else 0.0,
                    'sale_ok': True,
                    'purchase_ok': True,
                    'detailed_type': 'product',  # Odoo 19'da type yerine detailed_type
                }

                if default_code:
                    vals['default_code'] = default_code

                if barcode:
                    # Barcode benzersizliği kontrol et
                    existing = ProductTemplate.search([('barcode', '=', barcode)], limit=1)
                    if existing:
                        logger.warning(f"⚠️  Satır {i}: Barcode {barcode} zaten var, atlanıyor")
                        skipped += 1
                        continue
                    vals['barcode'] = barcode

                # Oluştur
                product = ProductTemplate.create(vals)
                created += 1

                if i % 50 == 0:
                    cr.commit()  # Her 50 kayıtta commit
                    logger.info(f"  ✅ {i} ürün işlendi, {created} oluşturuldu...")

            except Exception as e:
                skipped += 1
                error_msg = f"Satır {i}: {str(e)[:100]}"
                errors.append(error_msg)
                if len(errors) <= 10:
                    logger.error(f"  ❌ {error_msg}")

    # Final commit
    cr.commit()

    logger.info(f"\n✅ ÜRÜN ŞABLONLARI TAMAMLANDI:")
    logger.info(f"   ✅ Oluşturulan: {created}")
    logger.info(f"   ⏭️  Atlanan: {skipped}")

    if errors:
        logger.warning(f"\n⚠️  HATALAR ({len(errors)} adet):")
        for err in errors[:10]:
            logger.warning(f"   - {err}")

    return created

def import_variants(env, cr):
    """Ürün varyantlarını yükle"""
    logger.info("\n" + "="*60)
    logger.info("🎨 ÜRÜN VARYANTLARI YÜKLEME BAŞLIYOR...")
    logger.info("="*60)

    created = 0
    skipped = 0
    errors = []

    ProductTemplate = env['product.template']
    ProductProduct = env['product.product']
    AttributeValue = env['product.attribute.value']

    with open(VARIANTS_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for i, row in enumerate(reader, 1):
            try:
                template_code = row.get('product_tmpl_id/default_code', '').strip()
                color_name = row.get('attribute_value_ids/name', '').strip()
                variant_code = row.get('default_code', '').strip() or False
                barcode = row.get('barcode', '').strip() or False

                if not template_code or not color_name:
                    skipped += 1
                    continue

                # Template bul
                template = ProductTemplate.search([('default_code', '=', template_code)], limit=1)
                if not template:
                    error_msg = f"Satır {i}: Template '{template_code}' bulunamadı"
                    errors.append(error_msg)
                    logger.warning(f"  ⚠️  {error_msg}")
                    skipped += 1
                    continue

                # Renk attribute value bul
                color_attr = AttributeValue.search([
                    ('name', '=', color_name),
                    ('attribute_id.name', '=', 'Renk')
                ], limit=1)

                if not color_attr:
                    error_msg = f"Satır {i}: Renk '{color_name}' bulunamadı"
                    errors.append(error_msg)
                    logger.warning(f"  ⚠️  {error_msg}")
                    skipped += 1
                    continue

                # Varyant oluştur
                vals = {
                    'product_tmpl_id': template.id,
                    'product_template_attribute_value_ids': [(6, 0, [color_attr.id])],
                }

                if variant_code:
                    vals['default_code'] = variant_code

                if barcode:
                    # Barcode benzersizliği kontrol et
                    existing = ProductProduct.search([('barcode', '=', barcode)], limit=1)
                    if existing:
                        logger.warning(f"⚠️  Satır {i}: Barcode {barcode} zaten var, atlanıyor")
                        skipped += 1
                        continue
                    vals['barcode'] = barcode

                # Oluştur
                variant = ProductProduct.create(vals)
                created += 1

                if i % 10 == 0:
                    cr.commit()
                    logger.info(f"  ✅ {i} varyant işlendi, {created} oluşturuldu...")

            except Exception as e:
                skipped += 1
                error_msg = f"Satır {i}: {str(e)[:100]}"
                errors.append(error_msg)
                logger.error(f"  ❌ {error_msg}")

    # Final commit
    cr.commit()

    logger.info(f"\n✅ ÜRÜN VARYANTLARI TAMAMLANDI:")
    logger.info(f"   ✅ Oluşturulan: {created}")
    logger.info(f"   ⏭️  Atlanan: {skipped}")

    if errors:
        logger.warning(f"\n⚠️  HATALAR ({len(errors)} adet):")
        for err in errors[:10]:
            logger.warning(f"   - {err}")

    return created

def verify_import(env):
    """Yüklemeyi doğrula"""
    logger.info("\n" + "="*60)
    logger.info("✅ DOĞRULAMA...")
    logger.info("="*60)

    template_count = env['product.template'].search_count([])
    product_count = env['product.product'].search_count([])

    # Barcode duplicates
    products = env['product.product'].search([('barcode', '!=', False)])
    barcodes = products.mapped('barcode')
    duplicates = len(barcodes) - len(set(barcodes))

    logger.info(f"   📦 Toplam Ürün Şablonları: {template_count}")
    logger.info(f"   🎨 Toplam Ürün (variants dahil): {product_count}")
    logger.info(f"   🔢 Varyant Sayısı: {product_count - template_count}")
    logger.info(f"   ⚠️  Barcode Çakışması: {duplicates}")

    return template_count, product_count, duplicates

def main():
    logger.info("="*60)
    logger.info("🚀 JOKER GRUBU - ÜRÜN YÜKLEME (Direkt DB)")
    logger.info("="*60)

    try:
        # Odoo env yükle
        env, cr = load_odoo_env()
        logger.info("✅ Odoo environment yüklendi (DB: Joker)")

        # Templates yükle
        template_created = import_templates(env, cr)

        # Variants yükle
        variant_created = import_variants(env, cr)

        # Doğrula
        template_count, product_count, duplicates = verify_import(env)

        # Özet
        logger.info("\n" + "="*60)
        logger.info("📊 YÜKLEME ÖZETİ")
        logger.info("="*60)
        logger.info(f"✅ Toplam Ürün Şablonları: {template_count}")
        logger.info(f"✅ Toplam Varyantlar: {product_count - template_count}")
        logger.info(f"✅ Barcode Çakışması: {duplicates}")

        if duplicates == 0 and template_count >= 290:
            logger.info("\n✅✅✅ YÜKLEME BAŞARILI! Ürünler Joker DB'de hazır.")
        else:
            logger.warning(f"\n⚠️  Kontrol gerekli!")

    except Exception as e:
        logger.error(f"\n❌ HATA: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
