#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hesapları DOĞRU FORMATTA ekle - Odoo shell içinde çalışır
"""

import csv

Account = env['account.account']
IrModelData = env['ir.model.data']

print("="*100)
print("📋 HESAP EKLEME - DOĞRU FORMAT")
print("="*100)

def create_account_proper(external_id, code, name_tr, account_type, reconcile_bool):
    """Hesabı Odoo ORM ile doğru şekilde oluştur"""
    try:
        # External ID kontrol
        existing = IrModelData.search([
            ('module', '=', 'custom'),
            ('name', '=', external_id),
            ('model', '=', 'account.account')
        ], limit=1)

        if existing:
            print(f"⏭️  {code} - {name_tr[:50]} (zaten mevcut)")
            return None

        # DOĞRU YÖNTEM: code ve name direkt kullan, Odoo JSONB'ye çevirir
        account = Account.create({
            'code': code,
            'name': name_tr,
            'account_type': account_type,
            'reconcile': reconcile_bool,
        })

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
print("\n📊 EKSİK HESAPLAR EKLENİYOR...")
print("-"*100)

csv_file_1 = '/mnt/extra-addons/eksik_hesaplar_import.csv'
created_1 = 0

with open(csv_file_1, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        result = create_account_proper(
            row['external_id'].strip(),
            row['code'].strip(),
            row['name_tr'].strip(),
            row['account_type'].strip(),
            row['reconcile'].strip().upper() == 'TRUE'
        )
        if result:
            created_1 += 1

env.cr.commit()
print(f"\n✅ Eksik Hesaplar: {created_1} oluşturuldu")

# Banka hesaplarını ekle
print("\n🏦 BANKA HESAPLARI EKLENİYOR...")
print("-"*100)

csv_file_2 = '/mnt/extra-addons/banka_hesaplari_import.csv'
created_2 = 0

with open(csv_file_2, 'r', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        result = create_account_proper(
            row['external_id'].strip(),
            row['code'].strip(),
            row['name_tr'].strip(),
            row['account_type'].strip(),
            row['reconcile'].strip().upper() == 'TRUE'
        )
        if result:
            created_2 += 1

env.cr.commit()

print(f"\n✅ Banka Hesapları: {created_2} oluşturuldu")

print("\n" + "="*100)
print(f"📊 TOPLAM: {created_1 + created_2} hesap eklendi")
print("="*100)
