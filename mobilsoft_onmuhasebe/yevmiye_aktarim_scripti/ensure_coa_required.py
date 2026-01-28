#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kalan yılların yevmiye importu öncesi gerekli hesapları (account.account) hazırlar.

Kaynak:
- /joker/Mimar/sirket_verileri/Prepared/coa_required_from_2019_2025_journal.csv

Davranış:
- Odoo içindeki mevcut hesap kodlarını okur.
- CSV'deki hesap kodu yoksa oluşturur (name + account_type).
- account_type: aynı prefix'in (xxx000) hesabı varsa ondan alınır; yoksa ilk haneye göre tahmin edilir.

Not:
- Bu script Odoo içinde çalışır (docker exec odoo shell).
"""

from __future__ import annotations

import argparse
import csv
import subprocess
from pathlib import Path


DB_NAME = "Joker"
ODOO_CONF = "/etc/odoo/odoo.conf"
CONTAINER = "joker-odoo"

COA_REQUIRED = Path("/joker/Mimar/sirket_verileri/Prepared/coa_required_from_2019_2025_journal.csv")


def run_odoo(py: str, *, timeout_s: int = 1800) -> subprocess.CompletedProcess[str]:
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


def load_required() -> list[tuple[str, str]]:
    rows = []
    with COA_REQUIRED.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            code = (row.get("code") or "").strip()
            name = (row.get("name") or "").strip()
            if code and name:
                rows.append((code, name))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--execute", action="store_true", help="Hesapları oluştur (varsayılan: dry-run)")
    args = ap.parse_args()

    required = load_required()
    codes_py = "[" + ",".join(repr(c) for c, _ in required) + "]"
    names_py = "{" + ",".join(f"{c!r}:{n!r}" for c, n in required) + "}"

    py = "\n".join(
        [
            f"DO_EXECUTE = {bool(args.execute)}",
            f"REQ_CODES = {codes_py}",
            f"REQ_NAMES = {names_py}",
            "Account = env['account.account']",
            "existing = set(Account.search([('code','in',REQ_CODES)]).mapped('code'))",
            "missing = [c for c in REQ_CODES if c not in existing]",
            "print('EXISTING', len(existing), 'MISSING', len(missing))",
            "if not DO_EXECUTE:",
            "    for c in missing[:50]:",
            "        print('MISSING_CODE', c, REQ_NAMES.get(c,''))",
            "else:",
            "    # infer account_type from parent (xxx000) if possible",
            "    parent_map = {}",
            "    parents = Account.search([('code','like','___000')])",
            "    for p in parents:",
            "        parent_map[p.code[:3]] = p",
            "    type_map = {",
            "        '1': 'asset_current',",
            "        '2': 'asset_fixed',",
            "        '3': 'liability_current',",
            "        '4': 'liability_non_current',",
            "        '5': 'equity',",
            "        '6': 'income',",
            "        '7': 'expense',",
            "        '8': 'off_balance',",
            "        '9': 'off_balance',",
            "    }",
            "    created = 0",
            "    for code in missing:",
            "        name = REQ_NAMES.get(code) or ('Hesap ' + code)",
            "        # account_type: güvenli varsayım (ilk hane) + özel durumlar",
            "        if code.startswith('120'):",
            "            account_type = 'asset_receivable'",
            "        elif code.startswith('320'):",
            "            account_type = 'liability_payable'",
            "        else:",
            "            account_type = type_map.get(code[:1], 'expense')",
            "        reconcile = account_type in ('asset_receivable', 'liability_payable')",
            "        acc = Account.create({'code': code, 'name': name, 'account_type': account_type, 'reconcile': reconcile})",
            "        created += 1",
            "    env.cr.commit()",
            "    print('CREATED', created)",
        ]
    )

    res = run_odoo(py, timeout_s=3600)
    if res.returncode != 0:
        print(res.stdout)
        print(res.stderr)
        return res.returncode
    print(res.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
