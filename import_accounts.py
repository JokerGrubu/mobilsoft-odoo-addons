#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Eksik hesapları ve banka hesaplarını Odoo'ya ekle
"""

import csv
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def load_odoo_env():
    """Odoo environment'ı yükle"""
    try:
        import odoo
        from odoo.api import Environment
        from odoo.modules.registry import Registry

        db_name = 'Joker'
        registry = Registry(db_name)

        with registry.cursor() as cr:
            env = Environment(cr, 1, {})  # SUPERUSER_ID = 1
            return env, cr
    except Exception as e:
        logger.error(f"Odoo environment yüklenemedi: {e}")
        sys.exit(1)

def create_account(env, cr, external_id, code, name_tr, name_en, account_type, reconcile, company_id):
    """Tek bir hesap oluştur"""
    try:
        Account = env['account.account']
        IrModelData = env['ir.model.data']

        # External ID var mı kontrol et
        existing = IrModelData.search([
            ('module', '=', 'custom'),
            ('name', '=', external_id),
            ('model', '=', 'account.account')
        ], limit=1)

        if existing:
            logger.warning(f"⚠️  {code} - {name_tr} zaten mevcut (External ID: {external_id})")
            return None

        # Kod zaten var mı kontrol et
        existing_account = Account.search([
            ('code_store', '=', {str(company_id): code})
        ], limit=1)

        if existing_account:
            logger.warning(f"⚠️  {code} - {name_tr} zaten mevcut (Kod kontrolü)")
            return None

        # Hesap oluştur
        account_vals = {
            'code_store': {str(company_id): code},
            'name': {
                'tr_TR': name_tr,
                'en_US': name_en
            },
            'account_type': account_type,
            'reconcile': reconcile == 'TRUE',
        }

        account = Account.create(account_vals)

        # External ID oluştur
        IrModelData.create({
            'module': 'custom',
            'name': external_id,
            'model': 'account.account',
            'res_id': account.id,
        })

        logger.info(f"✅ {code:8s} - {name_tr[:60]:60s} ({account_type})")
        return account

    except Exception as e:
        logger.error(f"❌ {code} - {name_tr}: {str(e)[:100]}")
        return None

def import_accounts_from_csv(env, cr, csv_file):
    """CSV dosyasından hesapları import et"""
    created_count = 0
    skipped_count = 0
    error_count = 0

    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)

        for row in reader:
            external_id = row['external_id'].strip()
            code = row['code'].strip()
            name_tr = row['name_tr'].strip()
            name_en = row['name_en'].strip()
            account_type = row['account_type'].strip()
            reconcile = row['reconcile'].strip().upper()
            company_id = int(row['company_id'].strip())

            result = create_account(env, cr, external_id, code, name_tr, name_en, account_type, reconcile, company_id)

            if result:
                created_count += 1
                # Her 5 hesapta bir commit
                if created_count % 5 == 0:
                    cr.commit()
            elif result is None and "zaten mevcut" in str(result):
                skipped_count += 1
            else:
                error_count += 1

    # Final commit
    cr.commit()

    return created_count, skipped_count, error_count

def main():
    logger.info("="*100)
    logger.info("📋 ODOO HESAP PLANI GÜNCELLEME")
    logger.info("="*100)

    try:
        env, cr = load_odoo_env()
        logger.info("✅ Odoo environment yüklendi (DB: Joker)\n")

        # Eksik hesapları ekle
        logger.info("="*100)
        logger.info("📊 EKSİK HESAPLAR EKLENİYOR...")
        logger.info("="*100)

        csv_file_1 = '/mnt/extra-addons/eksik_hesaplar_import.csv'
        created_1, skipped_1, error_1 = import_accounts_from_csv(env, cr, csv_file_1)

        logger.info(f"\n✅ Eksik Hesaplar:")
        logger.info(f"   ✅ Oluşturulan: {created_1}")
        logger.info(f"   ⏭️  Atlanan: {skipped_1}")
        logger.info(f"   ❌ Hata: {error_1}")

        # Banka hesaplarını ekle
        logger.info("\n" + "="*100)
        logger.info("🏦 BANKA HESAPLARI EKLENİYOR...")
        logger.info("="*100)

        csv_file_2 = '/mnt/extra-addons/banka_hesaplari_import.csv'
        created_2, skipped_2, error_2 = import_accounts_from_csv(env, cr, csv_file_2)

        logger.info(f"\n✅ Banka Hesapları:")
        logger.info(f"   ✅ Oluşturulan: {created_2}")
        logger.info(f"   ⏭️  Atlanan: {skipped_2}")
        logger.info(f"   ❌ Hata: {error_2}")

        # Özet
        logger.info("\n" + "="*100)
        logger.info("📊 ÖZET")
        logger.info("="*100)
        logger.info(f"✅ Toplam Oluşturulan: {created_1 + created_2}")
        logger.info(f"⏭️  Toplam Atlanan: {skipped_1 + skipped_2}")
        logger.info(f"❌ Toplam Hata: {error_1 + error_2}")

        if (error_1 + error_2) == 0:
            logger.info("\n✅✅✅ BAŞARILI! Tüm hesaplar eklendi.")
        else:
            logger.warning(f"\n⚠️  {error_1 + error_2} hata oluştu, kontrol edin!")

        logger.info("="*100)

    except Exception as e:
        logger.error(f"\n❌ HATA: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
