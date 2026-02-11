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
        r.append(f"qnb_auto_fetch_outgoing: {getattr(c,'qnb_auto_fetch_outgoing','-')}")
        jp = J.search([('type','=','purchase'),('company_id','=',c.id)], limit=1)
        js = J.search([('type','=','sale'),('company_id','=',c.id)], limit=1)
        r.append(f"Alis fis: {'OK ' + jp.name if jp else 'YOK!'}")
        r.append(f"Satis fis: {'OK ' + js.name if js else 'YOK!'}")
        lfi = P.get_param(f"qnb_incoming_last_fetch_date.{c.id}") or "(hic)"
        lfo = P.get_param(f"qnb_outgoing_last_fetch_date.{c.id}") or "(hic)"
        r.append(f"Son cekim GELEN: {lfi}")
        r.append(f"Son cekim GIDEN: {lfo}")
        dd = fields.Date.today() - timedelta(days=30)
        inv_in = Mv.search([('company_id','=',c.id),('move_type','=','in_invoice'),('qnb_ettn','!=',False),('invoice_date','>=',dd)])
        inv_out = Mv.search([('company_id','=',c.id),('move_type','in',['out_invoice','out_refund']),('qnb_ettn','!=',False),('invoice_date','>=',dd)])
        r.append(f"Son 30 gun QNB gelen: {len(inv_in)}")
        r.append(f"Son 30 gun QNB giden: {len(inv_out)}")
        cr_in = Cr.search([('name','ilike','QNB'),('name','ilike','Gelen'),('active','=',True)], limit=1)
        cr_out = Cr.search([('name','ilike','QNB'),('name','ilike','Giden'),('active','=',True)], limit=1)
        r.append(f"Cron Gelen: {'OK' if cr_in else 'BULUNAMADI'}")
        r.append(f"Cron Giden: {'OK' if cr_out else 'BULUNAMADI'}")
    r.append("=" * 55)
    return "\n".join(r)

if 'env' in dir(): print(_run(env))
else: print("Odoo shell icinde calistirin.")
