#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Odoo hesap planını kontrol et - Kıta 2KB hesapları ve özellikleri
"""

import sys
import logging
import csv

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def load_odoo_env():
    """Odoo environment'ı yükle"""
    import odoo
    from odoo import api, SUPERUSER_ID

    db_name = 'joker'  # Küçük j - Odoo DB adı

    # Odoo registry'yi yükle
    registry = odoo.registry(db_name)

    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        return env, cr

def check_accounts(env):
    """Mevcut hesap planını detaylı kontrol et"""
    logger.info("="*100)
    logger.info("📋 ODOO HESAP PLANI ANALİZİ (Joker DB)")
    logger.info("="*100)

    Account = env['account.account']

    # Tüm hesapları al
    accounts = Account.search([], order='code')

    logger.info(f"\n✅ Toplam Hesap Sayısı: {len(accounts)}")

    # Hesapları gruplara ayır
    groups = {}
    account_types = {}
    reconcile_accounts = []

    for acc in accounts:
        # Kod prefix'ine göre grupla
        prefix = acc.code[:1] if acc.code else '0'
        if prefix not in groups:
            groups[prefix] = []
        groups[prefix].append(acc)

        # Account type'a göre grupla
        if acc.account_type not in account_types:
            account_types[acc.account_type] = []
        account_types[acc.account_type].append(acc)

        # Mutabakat gerektiren hesapları topla
        if acc.reconcile:
            reconcile_accounts.append(acc)

    # Grupları göster
    logger.info("\n" + "="*100)
    logger.info("📊 HESAP GRUPLARI (Kod Prefix'ine Göre):")
    logger.info("="*100)

    group_names = {
        '1': '💰 Dönen Varlıklar',
        '2': '🏢 Duran Varlıklar',
        '3': '📋 Kısa Vadeli Yabancı Kaynaklar',
        '4': '📅 Uzun Vadeli Yabancı Kaynaklar',
        '5': '💎 Özkaynaklar',
        '6': '📈 Gelir Tablosu',
        '7': '🏭 Maliyet Hesapları',
        '9': '📝 Nazım Hesaplar'
    }

    for prefix in sorted(groups.keys()):
        group_name = group_names.get(prefix, f'Grup {prefix}')
        count = len(groups[prefix])
        logger.info(f"  {group_name}: {count} hesap")

    # Account Type'lara göre dağılım
    logger.info("\n" + "="*100)
    logger.info("🏷️  ACCOUNT TYPE DAĞILIMI:")
    logger.info("="*100)

    for acc_type in sorted(account_types.keys()):
        count = len(account_types[acc_type])
        logger.info(f"  {acc_type:30s}: {count:3d} hesap")

    # Önemli hesaplar
    logger.info("\n" + "="*100)
    logger.info("📌 ÖNEMLİ HESAPLAR (Luca ile Eşleştirilecek):")
    logger.info("="*100)
    logger.info(f"{'Kod':10s} {'Hesap Adı':50s} {'Type':25s} {'Mut.':5s}")
    logger.info("-"*100)

    important_codes = [
        '100001', '101000', '102001', '108000',  # Hazır değerler
        '120000', '121000',  # Alıcılar
        '150000', '153000', '157000',  # Stoklar
        '191000',  # İndirilecek KDV
        '254000', '255000', '257000',  # Sabit kıymetler
        '320000', '321000',  # Satıcılar
        '360000', '391000',  # Vergiler
        '500000', '570000', '580000', '590000',  # Özkaynaklar
        '600000', '601000', '610000',  # Satışlar
        '620000', '621000',  # Maliyetler
        '631000', '632000'   # Giderler
    ]

    for code in important_codes:
        acc = Account.search([('code', '=', code)], limit=1)
        if acc:
            reconcile_str = '✓' if acc.reconcile else '✗'
            logger.info(f"{acc.code:10s} {acc.name[:48]:50s} {acc.account_type:25s} {reconcile_str:5s}")
        else:
            logger.info(f"{code:10s} {'❌ BULUNAMADI':50s} {'-':25s} {'-':5s}")

    # Mutabakat gerektiren hesaplar
    logger.info("\n" + "="*100)
    logger.info("🔄 MUTABAKAT GEREKTİREN HESAPLAR:")
    logger.info("="*100)
    logger.info(f"Toplam: {len(reconcile_accounts)} hesap")
    logger.info(f"\n{'Kod':10s} {'Hesap Adı':50s} {'Type':25s}")
    logger.info("-"*100)

    for acc in reconcile_accounts[:15]:  # İlk 15 tanesini göster
        logger.info(f"{acc.code:10s} {acc.name[:48]:50s} {acc.account_type:25s}")

    if len(reconcile_accounts) > 15:
        logger.info(f"  ... ve {len(reconcile_accounts) - 15} hesap daha")

    # CSV export (analiz için)
    csv_path = '/joker/Mimar/sirket_verileri/odoo_hesap_plani_mevcut.csv'
    logger.info(f"\n📁 Tüm hesaplar CSV'ye yazılıyor: {csv_path}")

    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Kod', 'Hesap Adı', 'Account Type', 'Reconcile', 'Deprecated', 'Company ID'])

        for acc in accounts:
            writer.writerow([
                acc.code or '',
                acc.name or '',
                acc.account_type or '',
                'Evet' if acc.reconcile else 'Hayır',
                'Evet' if acc.deprecated else 'Hayır',
                acc.company_id.name if acc.company_id else ''
            ])

    logger.info(f"✅ CSV oluşturuldu: {len(accounts)} hesap")

    return len(accounts), account_types, reconcile_accounts

def main():
    try:
        env, cr = load_odoo_env()
        logger.info("✅ Odoo environment yüklendi (DB: joker)\n")

        account_count, account_types, reconcile_accounts = check_accounts(env)

        logger.info("\n" + "="*100)
        logger.info("✅ KONTROL TAMAMLANDI")
        logger.info("="*100)
        logger.info(f"📊 Toplam Hesap: {account_count}")
        logger.info(f"🏷️  Account Type Çeşidi: {len(account_types)}")
        logger.info(f"🔄 Mutabakat Gerektiren: {len(reconcile_accounts)}")
        logger.info("\n💡 Sonraki Adım: Luca verilerini bu yapıya göre eşleştireceğiz")
        logger.info("="*100)

    except Exception as e:
        logger.error(f"\n❌ HATA: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
