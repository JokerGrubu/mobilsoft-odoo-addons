#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Veri çekme ve gerçek kontrol - Sync'leri ÇALIŞTIRIR, sonuçları doğrular.
  docker exec -it joker-odoo odoo shell -d Joker -c /etc/odoo/odoo.conf
  >>> exec(open('/mnt/extra-addons/veri_cek_kontrol.py').read())
"""

def _run(env):
    from datetime import timedelta
    from odoo import fields
    r = []
    r.append("=" * 70)
    r.append("VERİ ÇEKME VE DOĞRULAMA (Gerçek çalıştırma + sonuç kontrolü)")
    r.append("=" * 70)
    
    Mv = env['account.move']
    Partner = env['res.partner']
    Co = env['res.company']
    Param = env['ir.config_parameter'].sudo()
    
    # Şirket seç (QNB etkin)
    company = Co.search([('qnb_enabled', '=', True)], limit=1)
    if not company:
        r.append("\nQNB etkin şirket yok.")
        return "\n".join(r)
    
    # Company context - fetch metodları env.company kullanıyor
    ctx = dict(env.context, allowed_company_ids=[company.id])
    
    # ═══════════════════════════════════════════════════════════════
    # 1. QNB GELEN - ÖNCE/SONRA
    # ═══════════════════════════════════════════════════════════════
    r.append("\n" + "-" * 50)
    r.append("1. QNB GELEN FATURALAR - ÇEKME ÇALIŞTIRILIYOR")
    r.append("-" * 50)
    
    before_in = Mv.search_count([
        ('company_id', '=', company.id),
        ('move_type', '=', 'in_invoice'),
        ('qnb_ettn', '!=', False),
    ])
    r.append(f"Önce gelen fatura sayısı (QNB): {before_in}")
    
    try:
        env['account.move'].with_context(ctx)._qnb_fetch_incoming_documents()
        after_in = Mv.search_count([
            ('company_id', '=', company.id),
            ('move_type', '=', 'in_invoice'),
            ('qnb_ettn', '!=', False),
        ])
        new_in = after_in - before_in
        r.append(f"Sonra: {after_in} | Yeni gelen: {new_in}")
        if new_in > 0:
            son_faturalar = Mv.search([
                ('company_id', '=', company.id),
                ('move_type', '=', 'in_invoice'),
                ('qnb_ettn', '!=', False),
            ], order='id desc', limit=3)
            for inv in son_faturalar:
                r.append(f"  -> {inv.name} | {inv.partner_id.name} | {inv.invoice_date}")
        else:
            r.append("  (Yeni fatura gelmedi - API'de yeni belge olmayabilir)")
    except Exception as e:
        r.append(f"HATA: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # 2. QNB GİDEN - ÖNCE/SONRA
    # ═══════════════════════════════════════════════════════════════
    r.append("\n" + "-" * 50)
    r.append("2. QNB GİDEN FATURALAR - ÇEKME ÇALIŞTIRILIYOR")
    r.append("-" * 50)
    
    before_out = Mv.search_count([
        ('company_id', '=', company.id),
        ('move_type', 'in', ['out_invoice', 'out_refund']),
        ('qnb_ettn', '!=', False),
    ])
    r.append(f"Önce giden fatura sayısı (QNB): {before_out}")
    
    try:
        env['account.move'].with_context(ctx)._qnb_fetch_outgoing_documents(batch_size=50)
        after_out = Mv.search_count([
            ('company_id', '=', company.id),
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('qnb_ettn', '!=', False),
        ])
        new_out = after_out - before_out
        r.append(f"Sonra: {after_out} | Yeni gelen: {new_out}")
        if new_out > 0:
            son_faturalar = Mv.search([
                ('company_id', '=', company.id),
                ('move_type', 'in', ['out_invoice', 'out_refund']),
                ('qnb_ettn', '!=', False),
            ], order='id desc', limit=3)
            for inv in son_faturalar:
                r.append(f"  -> {inv.name} | {inv.partner_id.name} | {inv.invoice_date}")
    except Exception as e:
        r.append(f"HATA: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # 3. BİZİMHESAP - SENKRONIZASYON ÇALIŞTIR + PARTNER DURUMU
    # ═══════════════════════════════════════════════════════════════
    r.append("\n" + "-" * 50)
    r.append("3. BİZİMHESAP - SENKRONIZASYON + PARTNER GÜNCELLEME KONTROLÜ")
    r.append("-" * 50)
    
    try:
        BH = env['bizimhesap.backend']
        backend = BH.search([('active', '=', True), ('state', '=', 'connected')], limit=1)
        if not backend:
            r.append("Bağlı BizimHesap backend yok.")
        else:
            # Partner binding son güncellemeler
            Binding = env['bizimhesap.partner.binding']
            recent_bindings = Binding.search([], order='sync_date desc', limit=5)
            r.append(f"Son 5 partner binding (sync_date):")
            for b in recent_bindings:
                r.append(f"  -> {b.odoo_id.name} (ID:{b.odoo_id.id}) | sync: {b.sync_date}")
            
            # Sync çalıştır
            r.append("\n>>> Sync çalıştırılıyor...")
            backend.action_sync_all()
            r.append(">>> Sync tamamlandı.")
            
            # Sync sonrası - yeni güncellenen binding'ler
            recent_after = Binding.search([], order='sync_date desc', limit=5)
            r.append(f"\nSync sonrası son 5 partner binding:")
            for b in recent_after:
                r.append(f"  -> {b.odoo_id.name} | sync: {b.sync_date} | vat: {b.odoo_id.vat or '-'}")
            
            # Partner'da VKN/name boş olan ama BizimHesap'ta olan var mı?
            bh_partners = Partner.search([('bizimhesap_binding_ids', '!=', False)], limit=20)
            bos_vat = [p for p in bh_partners if not (p.vat or '').strip()]
            r.append(f"\nBizimHesap bağlı partnerlerden VKN boş: {len(bos_vat)}")
            if bos_vat and len(bos_vat) <= 5:
                for p in bos_vat[:5]:
                    r.append(f"  -> {p.name} (ID:{p.id})")
    except Exception as e:
        r.append(f"HATA: {e}")
        import traceback
        r.append(traceback.format_exc())
    
    # ═══════════════════════════════════════════════════════════════
    # 4. NİLVERA PARTNER GÜNCELLEME
    # ═══════════════════════════════════════════════════════════════
    r.append("\n" + "-" * 50)
    r.append("4. NİLVERA PARTNER GÜNCELLEME")
    r.append("-" * 50)
    
    try:
        Partner = env['res.partner']
        Co = env['res.company']
        # Nilvera API anahtarı var mı?
        has_key = bool(getattr(Co.search([], limit=1), 'l10n_tr_nilvera_api_key', None))
        r.append(f"Nilvera API anahtarı: {'Var' if has_key else 'YOK (Ayarlar > Faturalama > Nilvera)'}")
        
        # Cron var mı?
        Cr = env['ir.cron']
        cr_nilv = Cr.search([('name', 'ilike', 'Nilvera'), ('name', 'ilike', 'Cari')], limit=1)
        r.append(f"Nilvera partner cron: {'OK' if cr_nilv else 'BULUNAMADI'}")
        
        if has_key:
            r.append(">>> Nilvera partner güncelleme çalıştırılıyor...")
            partners = Partner.search([
                ('vat', '!=', False), ('vat', '!=', ''),
                '|', '|',
                ('street', 'in', [False, '']),
                ('city', 'in', [False, '']),
                ('phone', 'in', [False, '']),
            ], limit=10, order='id asc')
            r.append(f"  Örnek eksik bilgili partner: {len(partners)}")
            if partners:
                stats = Partner._do_batch_update_nilvera_only(partners)
                r.append(f"  İşlenen: {stats['processed']} | Güncellenen: {stats['updated']} | Hata: {stats['errors']}")
                if stats['updated'] > 0:
                    r.append("  >>> BAŞARILI - Partnerler güncellendi")
                else:
                    r.append("  (Güncellenen yok - API cevap vermemiş veya veri aynı olabilir)")
        else:
            r.append("  (API anahtarı yok - Nilvera partner güncelleme atlandı)")
    except Exception as e:
        r.append(f"HATA: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # 5. GELEN FATURALAR ODOO'DA NEREDE?
    # ═══════════════════════════════════════════════════════════════
    r.append("\n" + "-" * 50)
    r.append("5. GELEN FATURALAR - ODOO KONUMU")
    r.append("-" * 50)
    r.append("Muhasebe > Vendör Faturaları (in_invoice)")
    r.append("Filtre: qnb_ettn dolu olanlar = QNB'den gelen")
    son_gelen = Mv.search([
        ('company_id', '=', company.id),
        ('move_type', '=', 'in_invoice'),
        ('qnb_ettn', '!=', False),
    ], order='invoice_date desc', limit=5)
    r.append(f"Son 5 gelen fatura:")
    for inv in son_gelen:
        r.append(f"  {inv.name} | {inv.partner_id.name} | {inv.invoice_date} | ETTN: {inv.qnb_ettn[:20] if inv.qnb_ettn else '-'}...")
    
    r.append("\n" + "=" * 70)
    return "\n".join(r)

if 'env' in dir():
    print(_run(env))
else:
    print("Odoo shell icinde calistirin: exec(open('/mnt/extra-addons/veri_cek_kontrol.py').read())")
