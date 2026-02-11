#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QNB Gelen Belgeleri Manuel Cek - Son cekim tarihini bugune al ve cron'u calistir.
  docker exec -it joker-odoo odoo shell -d Joker -c /etc/odoo/odoo.conf
  >>> exec(open('/mnt/extra-addons/qnb_manual_fetch.py').read())
"""
def _run(env):
    from odoo import fields
    P = env['ir.config_parameter'].sudo()
    Co = env['res.company']
    cos = Co.search([('qnb_enabled','=',True),('qnb_auto_fetch_incoming','=',True)])
    for c in cos:
        key = f"qnb_incoming_last_fetch_date.{c.id}"
        old = P.get_param(key)
        new = (fields.Date.today() - __import__('datetime').timedelta(days=7)).strftime("%Y-%m-%d")
        P.set_param(key, new)
        print(f"{c.name}: {old} -> {new} (son 7 gun)")
    Move = env['account.move']
    for c in cos:
        Move.with_company(c)._qnb_fetch_incoming_documents()
    print("Cekim tamamlandi.")
    for c in cos:
        print(f"Yeni son cekim: {P.get_param(f'qnb_incoming_last_fetch_date.{c.id}')}")

if 'env' in dir(): _run(env)
else: print("Odoo shell icinde calistirin.")
