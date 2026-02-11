#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QNB Tanı - Odoo shell içinde çalıştır:
  docker exec -it joker-odoo odoo shell -d Joker -c /etc/odoo/odoo.conf
  >>> exec(open('/mnt/extra-addons/qnb_diagnostic.py').read())
"""

def _run(env):
    from datetime import timedelta
    from odoo import fields
    r = []
    r.append("=" * 55)
    r.append("QNB TANI KONTROLÜ")
    r.append("=" * 55)
    Co = env['res.company']
    Mv = env['account.move']
    J = env['account.journal']
    Cr = env['ir.cron']
    P = env['ir.config_parameter'].sudo()
    cos = Co.search([('qnb_enabled', '=', True)])
    if not cos:
        r.append("\n⚠ QNB etkin sirket yok.")
        return "\n".join(r)
    for c in cos:
        r.append(f"\n--- {c.name} ---")
        r.append(f"qnb_efatura_enabled: {c.qnb_efatura_enabled}")
        r.append(f"qnb_auto_fetch_incoming: {getattr(c,'qnb_auto_fetch_incoming','-')}")
        j = J.search([('type','=','purchase'),('company_id','=',c.id)], limit=1)
        r.append(f"Alis fis: {'OK ' + j.name if j else 'YOK!'}")
        lf = P.get_param(f"qnb_incoming_last_fetch_date.{c.id}") or "(hic)"
        r.append(f"Son cekim: {lf}")
        dd = fields.Date.today() - timedelta(days=30)
        invs = Mv.search([('company_id','=',c.id),('move_type','=','in_invoice'),('qnb_ettn','!=',False),('invoice_date','>=',dd)], limit=5)
        r.append(f"Son 30 gun QNB gelen: {len(invs)}")
        cr = Cr.search([('name','ilike','QNB'),('name','ilike','Gelen'),('active','=',True)], limit=1)
        r.append(f"Cron: {'OK' if cr else 'BULUNAMADI'}")
    r.append("=" * 55)
    return "\n".join(r)

if 'env' in dir(): print(_run(env))
else: print("Odoo shell icinde calistirin.")
