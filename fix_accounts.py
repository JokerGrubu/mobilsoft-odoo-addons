#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Yanlış eklenen hesapları sil ve doğru formatta tekrar ekle
Odoo shell içinden çalıştırılmalı
"""

import csv
import json

print("="*100)
print("🔧 YANLIŞ HESAPLARI DÜZELTİYORUZ")
print("="*100)

# Yanlış eklenen hesapları bul ve sil
print("\n❌ Yanlış hesapları buluyoruz...")

Account = env['account.account']
IrModelData = env['ir.model.data']

# Yanlış format: code_store içinde string olarak dictionary
wrong_accounts = Account.search([
    ('code_store', 'ilike', "{'1':")
])

print(f"Bulundu: {len(wrong_accounts)} yanlış hesap")

if wrong_accounts:
    print("\n❌ Yanlış hesaplar siliniyor...")
    for acc in wrong_accounts:
        code = str(acc.code_store)
        name = str(acc.name)
        print(f"  Siliniyor: {code[:50]}")

        # External ID'yi de sil
        ext_ids = IrModelData.search([
            ('model', '=', 'account.account'),
            ('res_id', '=', acc.id)
        ])
        if ext_ids:
            ext_ids.unlink()

        acc.unlink()

    env.cr.commit()
    print(f"✅ {len(wrong_accounts)} hesap silindi")

# Şimdi doğru formatta ekle
print("\n" + "="*100)
print("✅ HESAPLARI DOĞRU FORMATTA EKLİYORUZ")
print("="*100)

def create_account_correct(external_id, code, name_tr, name_en, account_type, reconcile_bool, company_id):
    """Hesabı doğru JSONB formatında oluştur"""
    try:
        # External ID var mı kontrol et
        existing = IrModelData.search([
            ('module', '=', 'custom'),
            ('name', '=', external_id),
            ('model', '=', 'account.account')
        ], limit=1)

        if existing:
            print(f"⚠️  {code} zaten mevcut, atlanıyor")
            return None

        # DOĞRU format: code_store ve name JSONB olarak
        account_vals = {
            'code_store': {str(company_id): code},  # Dict olarak, string değil!
            'name': {'tr_TR': name_tr, 'en_US': name_en},  # Dict olarak, string değil!
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
        print(f"❌ {code} - {name_tr}: {str(e)[:150]}")
        return None

# Eksik hesapları ekle
print("\n📊 EKSİK HESAPLAR...")
csv_file_1 = '/mnt/extra-addons/eksik_hesaplar_import.csv'
created_1 = 0

with open(csv_file_1, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        result = create_account_correct(
            row['external_id'].strip(),
            row['code'].strip(),
            row['name_tr'].strip(),
            row['name_en'].strip(),
            row['account_type'].strip(),
            row['reconcile'].strip().upper() == 'TRUE',
            int(row['company_id'].strip())
        )
        if result:
            created_1 += 1

env.cr.commit()
print(f"\n✅ Eksik Hesaplar: {created_1} oluşturuldu")

# Banka hesaplarını ekle
print("\n🏦 BANKA HESAPLARI...")
csv_file_2 = '/mnt/extra-addons/banka_hesaplari_import.csv'
created_2 = 0

with open(csv_file_2, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        result = create_account_correct(
            row['external_id'].strip(),
            row['code'].strip(),
            row['name_tr'].strip(),
            row['name_en'].strip(),
            row['account_type'].strip(),
            row['reconcile'].strip().upper() == 'TRUE',
            int(row['company_id'].strip())
        )
        if result:
            created_2 += 1

env.cr.commit()
print(f"\n✅ Banka Hesapları: {created_2} oluşturuldu")

print("\n" + "="*100)
print("📊 ÖZET")
print("="*100)
print(f"✅ Toplam Oluşturulan: {created_1 + created_2}")
print("="*100)
