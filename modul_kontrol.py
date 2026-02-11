#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Entegrasyon modülleri kontrol ve senkronizasyon testi
  docker exec -it joker-odoo odoo shell -d Joker -c /etc/odoo/odoo.conf
  >>> exec(open('/mnt/extra-addons/modul_kontrol.py').read())
"""

def _run(env):
    from datetime import timedelta
    from odoo import fields
    r = []
    errors = []
    
    r.append("=" * 60)
    r.append("ENTEGRASYON MODÜLLERİ KONTROLÜ")
    r.append("=" * 60)
    
    # ═══════════════════════════════════════════════════════════════
    # BİZİMHESAP
    # ═══════════════════════════════════════════════════════════════
    r.append("\n--- BİZİMHESAP ---")
    try:
        BH = env['bizimhesap.backend']
        backends = BH.search([('active', '=', True)])
        if not backends:
            r.append("  Kayıtlı backend yok.")
        else:
            for b in backends:
                r.append(f"\n  Backend: {b.name}")
                r.append(f"  Durum: {b.state or '-'}")
                r.append(f"  Cari sync: {'Açık' if b.sync_partner else 'Kapalı'}")
                r.append(f"  Ürün sync: {'Açık' if b.sync_product else 'Kapalı'}")
                r.append(f"  Fatura sync: {'Açık' if b.sync_invoice else 'Kapalı'}")
                r.append(f"  Otomatik sync: {'Açık' if b.auto_sync else 'Kapalı'}")
                r.append(f"  Son sync: {b.last_sync_date or '-'}")
                if b.state == 'connected' and b.auto_sync:
                    r.append("  >>> Sync çalıştırılıyor...")
                    try:
                        b.action_sync_all()
                        r.append("  >>> BAŞARILI")
                    except Exception as e:
                        errors.append(f"BizimHesap ({b.name}): {str(e)}")
                        r.append(f"  >>> HATA: {e}")
    except Exception as e:
        r.append(f"  Modül yüklenemiyor veya hata: {e}")
        errors.append(f"BizimHesap: {str(e)}")
    
    # ═══════════════════════════════════════════════════════════════
    # XML ÜRÜN İMPORT
    # ═══════════════════════════════════════════════════════════════
    r.append("\n--- XML ÜRÜN İMPORT ---")
    try:
        XML = env['xml.product.source']
        sources = XML.search([])
        if not sources:
            r.append("  Kayıtlı XML kaynağı yok.")
        else:
            auto_sources = sources.filtered(lambda s: s.state == 'active' and s.auto_sync)
            r.append(f"  Toplam kaynak: {len(sources)}")
            r.append(f"  Oto-sync açık: {len(auto_sources)}")
            for s in sources[:5]:
                r.append(f"  - {s.name}: state={s.state}, auto_sync={s.auto_sync}, son={s.last_sync or '-'}")
            if auto_sources:
                r.append("  >>> Sync çalıştırılıyor...")
                try:
                    XML.cron_sync_all_sources()
                    r.append("  >>> BAŞARILI")
                except Exception as e:
                    errors.append(f"XML Import: {str(e)}")
                    r.append(f"  >>> HATA: {e}")
    except Exception as e:
        r.append(f"  Modül yüklenemiyor veya hata: {e}")
        errors.append(f"XML Import: {str(e)}")
    
    # ═══════════════════════════════════════════════════════════════
    # QNB
    # ═══════════════════════════════════════════════════════════════
    r.append("\n--- QNB e-FATURA ---")
    try:
        Co = env['res.company']
        Mv = env['account.move']
        J = env['account.journal']
        Cr = env['ir.cron']
        P = env['ir.config_parameter'].sudo()
        cos = Co.search([('qnb_enabled', '=', True)])
        if not cos:
            r.append("  QNB etkin şirket yok.")
        else:
            for c in cos:
                r.append(f"\n  Şirket: {c.name}")
                r.append(f"  e-Fatura: {'Açık' if c.qnb_efatura_enabled else 'Kapalı'}")
                r.append(f"  Gelen oto: {'Açık' if getattr(c,'qnb_auto_fetch_incoming',False) else 'Kapalı'}")
                r.append(f"  Giden oto: {'Açık' if getattr(c,'qnb_auto_fetch_outgoing',False) else 'Kapalı'}")
                lfi = P.get_param(f"qnb_incoming_last_fetch_date.{c.id}") or "-"
                lfo = P.get_param(f"qnb_outgoing_last_fetch_date.{c.id}") or "-"
                r.append(f"  Son çekim gelen: {lfi}")
                r.append(f"  Son çekim giden: {lfo}")
                cr_in = Cr.search([('name','ilike','QNB'),('name','ilike','Gelen'),('active','=',True)], limit=1)
                cr_out = Cr.search([('name','ilike','QNB'),('name','ilike','Giden'),('active','=',True)], limit=1)
                r.append(f"  Cron gelen: {'OK' if cr_in else 'BULUNAMADI'}")
                r.append(f"  Cron giden: {'OK' if cr_out else 'BULUNAMADI'}")
    except Exception as e:
        r.append(f"  Hata: {e}")
        errors.append(f"QNB: {str(e)}")
    
    # ═══════════════════════════════════════════════════════════════
    # ÖZET
    # ═══════════════════════════════════════════════════════════════
    r.append("\n" + "=" * 60)
    if errors:
        r.append("HATALAR:")
        for e in errors:
            r.append(f"  - {e}")
    else:
        r.append("Tüm kontroller tamamlandı. Kritik hata yok.")
    r.append("=" * 60)
    return "\n".join(r)

if 'env' in dir():
    print(_run(env))
else:
    print("Odoo shell icinde calistirin: exec(open('/mnt/extra-addons/modul_kontrol.py').read())")
