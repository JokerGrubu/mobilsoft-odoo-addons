#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Partner temizlik (mükerrer birleştirme) aracı.

Hedef:
- Aynı VKN/TCKN (vat) ile mükerrer partnerları birleştir.
- Bugün otomatik oluşturulan basit partnerlar (vat boş / az alan) varsa,
  aynı isimle mükerrerleri birleştir ve güçlü eşleşme varsa mevcut partnere bağla.

Çıktılar:
- /joker/Mimar/sirket_verileri/Prepared/partner_cleanup_actions.csv

Notlar:
- Varsayılan davranış: DRY-RUN (sadece rapor).
- `--execute` verilirse merge işlemlerini yapar.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
from pathlib import Path


DB_NAME = "Joker"
ODOO_CONF = "/etc/odoo/odoo.conf"
CONTAINER = "joker-odoo"
OUT_FILE = Path("/joker/Mimar/sirket_verileri/Prepared/partner_cleanup_actions.csv")


def run_odoo_shell(py: str, *, timeout_s: int = 1800) -> subprocess.CompletedProcess[str]:
    cmd = [
        "docker",
        "exec",
        "-i",
        CONTAINER,
        "odoo",
        "shell",
        "-d",
        DB_NAME,
        "--no-http",
        "-c",
        ODOO_CONF,
    ]
    return subprocess.run(cmd, input=py, text=True, capture_output=True, timeout=timeout_s)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="Merge uygula (varsayılan: dry-run)")
    args = ap.parse_args()

    # Odoo içinde çalışacak kod:
    # - VAT digit normalize ile mükerrerleri bul
    # - dst partner seç (dolu alan sayısına göre)
    # - wizard ile merge
    # - bugünkü boş VAT partnerlar için isim bazlı mükerrerleri birleştir
    py = """
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher

DO_EXECUTE = __EXECUTE__
OUT_ROWS = []

VAT_DIGITS_RE = re.compile(r"\\D+")

TR_FOLD = str.maketrans("ÇĞİÖŞÜÂÊÎÔÛ", "CGIOSUAEIOU")
NON_ALNUM_RE = re.compile(r"[^0-9A-ZÇĞİÖŞÜ ]+", re.IGNORECASE)
SUFFIX_RE = re.compile(r"\\b(A\\.?\\s*Ş\\.?|AS|A\\.?S\\.?|LTD\\.?|LTD\\s*Ş\\.?T\\.?İ\\.?|LİMİTED|Ş\\.?T\\.?İ\\.?|STI|TİC\\.?|SAN\\.?|VE|V\\.)\\b", re.IGNORECASE)

def normalize_vat(raw):
    s = (raw or "").strip().upper()
    if not s:
        return ""
    if s.startswith("TR"):
        s = s[2:]
    digits = VAT_DIGITS_RE.sub("", s)
    if len(digits) == 9:
        digits = "0" + digits
    return digits

def normalize_name(raw):
    s = (raw or "").strip().upper()
    if not s:
        return ""
    s = NON_ALNUM_RE.sub(" ", s)
    s = SUFFIX_RE.sub(" ", s)
    s = " ".join(s.split())
    s = s.translate(TR_FOLD)
    return s

def similarity(a, b):
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()

Partner = env['res.partner']
Wizard = env['base.partner.merge.automatic.wizard']

def filled_score(p):
    # Basit doluluk skoru
    score = 0
    for f in ['vat','email','phone','mobile','website','street','street2','city','zip']:
        if getattr(p, f, False):
            score += 1
    # şirket/kişisel, rank
    if getattr(p, 'is_company', False):
        score += 1
    score += int(getattr(p, 'customer_rank', 0) or 0 > 0)
    score += int(getattr(p, 'supplier_rank', 0) or 0 > 0)
    # active
    score += 1 if p.active else 0
    return score

def merge_partners(dst_id, src_ids, reason):
    if not src_ids:
        return
    # Odoo güvenlik limiti: tek seferde en fazla 3 contact merge (dst dahil).
    pending = [i for i in src_ids if i != dst_id]
    while pending:
        batch_src = pending[:2]  # dst + 2 kaynak = 3
        pending = pending[2:]
        ids = [dst_id] + batch_src
        OUT_ROWS.append({
            'action': 'MERGE' if DO_EXECUTE else 'DRY_RUN',
            'reason': reason,
            'dst_partner_id': dst_id,
            'src_partner_ids': ','.join(str(i) for i in batch_src),
        })
        if not DO_EXECUTE:
            continue
        wiz = Wizard.create({
            'dst_partner_id': dst_id,
            'partner_ids': [(6, 0, ids)],
            'group_by_vat': False,
            'group_by_name': False,
            'group_by_email': False,
        })
        wiz.action_merge()
        env.cr.commit()

# 1) VAT bazlı mükerrerleri bul ve birleştir
partners_with_vat = Partner.search([('vat','!=',False)])
groups = {}
for p in partners_with_vat:
    vd = normalize_vat(p.vat)
    if not vd:
        continue
    groups.setdefault(vd, []).append(p)

for vd, plist in groups.items():
    if len(plist) < 2:
        continue
    plist = sorted(plist, key=lambda p: (filled_score(p), -p.id), reverse=True)
    dst = plist[0]
    src = [p.id for p in plist[1:]]
    merge_partners(dst.id, src, 'vat:%s' % vd)

# 2) Bugün otomatik oluşan (VAT boş) isim mükerrerlerini birleştir
since = datetime.utcnow() - timedelta(days=1)
recent = Partner.search([('create_date','>=', since.strftime('%Y-%m-%d %H:%M:%S')), ('vat','=',False)])

by_name = {}
for p in recent:
    nn = normalize_name(p.name)
    if not nn:
        continue
    by_name.setdefault(nn, []).append(p)

for nn, plist in by_name.items():
    if len(plist) < 2:
        continue
    plist = sorted(plist, key=lambda p: (filled_score(p), -p.id), reverse=True)
    dst = plist[0]
    src = [p.id for p in plist[1:]]
    merge_partners(dst.id, src, 'recent_name:%s' % nn)

env.cr.commit()

print('ACTIONS_COUNT', len(OUT_ROWS))
for r in OUT_ROWS:
    print(f\"{r['action']}\\t{r['reason']}\\tDST={r['dst_partner_id']}\\tSRC={r['src_partner_ids']}\")
"""
    py = py.replace("__EXECUTE__", str(bool(args.execute)))

    res = run_odoo_shell(py, timeout_s=3600)
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr)
        return res.returncode

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Parse stdout lines into a simple CSV (best-effort)
    rows = []
    for line in res.stdout.splitlines():
        if not line or line.startswith("ACTIONS_COUNT"):
            continue
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        action = parts[0]
        reason = parts[1]
        dst = parts[2].replace("DST=", "").strip()
        src = parts[3].replace("SRC=", "").strip()
        rows.append({"action": action, "reason": reason, "dst_partner_id": dst, "src_partner_ids": src})

    with OUT_FILE.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["action", "reason", "dst_partner_id", "src_partner_ids"])
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote: {OUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
