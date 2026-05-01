#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Eksik hesapları ve banka hesaplarını Odoo'ya ekle
Odoo shell içinden çalıştırılmalı
"""

import csv

def create_account(env, external_id, code, name_tr, name_en, account_type, reconcile_bool, company_id):
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
            print(f"⚠️  {code} - {name_tr} zaten mevcut (External ID: {external_id})")
            return None

        # Hesap oluştur
        account_vals = {
            'code_store': {str(company_id): code},
            'name': {
                'tr_TR': name_tr,
                'en_US': name_en
            },
            'account_type': account_type,
            'reconcile': reconcile_bool,
        }

        account = Account.create(account_vals)

        # External ID oluştur
        IrModelData.create({
            'module': 'custom',
            'name': external_id,
            'model': 'account.account',
            'res_id': account.id,
        })

        print(f"✅ {code:8s} - {name_tr[:60]}")
        return account

    except Exception as e:
        print(f"❌ {code} - {name_tr}: {str(e)[:100]}")
        return None

def import_accounts_from_csv(env, csv_file):
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
            reconcile_bool = row['reconcile'].strip().upper() == 'TRUE'
            company_id = int(row['company_id'].strip())

            result = create_account(env, external_id, code, name_tr, name_en, account_type, reconcile_bool, company_id)

            if result:
                created_count += 1
            elif result is None:
                skipped_count += 1
            else:
                error_count += 1

    env.cr.commit()

    return created_count, skipped_count, error_count

# Main execution
print("="*100)
print("📋 ODOO HESAP PLANI GÜNCELLEME")
print("="*100)

# Eksik hesapları ekle
print("\n" + "="*100)
print("📊 EKSİK HESAPLAR EKLENİYOR...")
print("="*100)

csv_file_1 = '/mnt/extra-addons/eksik_hesaplar_import.csv'
created_1, skipped_1, error_1 = import_accounts_from_csv(env, csv_file_1)

print(f"\n✅ Eksik Hesaplar:")
print(f"   ✅ Oluşturulan: {created_1}")
print(f"   ⏭️  Atlanan: {skipped_1}")
print(f"   ❌ Hata: {error_1}")

# Banka hesaplarını ekle
print("\n" + "="*100)
print("🏦 BANKA HESAPLARI EKLENİYOR...")
print("="*100)

csv_file_2 = '/mnt/extra-addons/banka_hesaplari_import.csv'
created_2, skipped_2, error_2 = import_accounts_from_csv(env, csv_file_2)

print(f"\n✅ Banka Hesapları:")
print(f"   ✅ Oluşturulan: {created_2}")
print(f"   ⏭️  Atlanan: {skipped_2}")
print(f"   ❌ Hata: {error_2}")

# Özet
print("\n" + "="*100)
print("📊 ÖZET")
print("="*100)
print(f"✅ Toplam Oluşturulan: {created_1 + created_2}")
print(f"⏭️  Toplam Atlanan: {skipped_1 + skipped_2}")
print(f"❌ Toplam Hata: {error_1 + error_2}")

if (error_1 + error_2) == 0:
    print("\n✅✅✅ BAŞARILI! Tüm hesaplar eklendi.")
else:
    print(f"\n⚠️  {error_1 + error_2} hata oluştu, kontrol edin!")

print("="*100)
