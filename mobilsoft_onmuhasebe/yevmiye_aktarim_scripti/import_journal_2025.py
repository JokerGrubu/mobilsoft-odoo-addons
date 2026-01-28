#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2025 yevmiye kayıtlarını Odoo'ya yükler
CSV Format: date,ref,journal_code,account_code,account_name,partner_vat,partner_name,label,debit,credit,luca_code,invoice_ref
"""

import pandas as pd
import argparse
import subprocess
import sys
from collections import defaultdict

CSV_FILE_DEFAULT = "/joker/Mimar/sirket_verileri/Prepared/journal_2025_prepared.csv"
DB_NAME = "Joker"

DEFAULT_BATCH_SIZE = 100  # Her seferde 100 fiş işle

def load_journal_entries(csv_file: str):
    """CSV dosyasından yevmiye kayıtlarını oku"""
    print(f"📖 CSV dosyası okunuyor: {csv_file}")
    df = pd.read_csv(csv_file, encoding='utf-8')

    # Bazı prepared dosyalar "Odoo import formatı" kolon adları ile gelebilir (örn. Ref, Journal/Code).
    # Bu durumda kolonları proje içi standart formata çevir.
    col_map = {c.strip().lower(): c for c in df.columns}

    def rename_if_present(target: str, *candidates: str):
        for cand in candidates:
            key = cand.strip().lower()
            if key in col_map:
                df.rename(columns={col_map[key]: target}, inplace=True)
                col_map[target] = target
                return

    # Standardize expected columns (case/format variants)
    rename_if_present('ref', 'ref')
    rename_if_present('ref', 'Ref')
    rename_if_present('date', 'date', 'Date')
    rename_if_present('journal_code', 'journal_code', 'Journal/Code', 'journal/code', 'Journal Code')
    rename_if_present('account_code', 'account_code', 'Account/Code', 'account/code', 'Account Code')
    rename_if_present('label', 'label', 'Label')
    rename_if_present('partner_name', 'partner_name', 'Partner')
    rename_if_present('debit', 'debit', 'Debit')
    rename_if_present('credit', 'credit', 'Credit')

    # Ensure required columns exist
    for required, default in [
        ('ref', ''),
        ('date', ''),
        ('journal_code', ''),
        ('account_code', ''),
        ('account_name', ''),
        ('partner_vat', ''),
        ('partner_name', ''),
        ('label', ''),
        ('debit', 0.0),
        ('credit', 0.0),
        ('invoice_ref', ''),
    ]:
        if required not in df.columns:
            df[required] = default

    print(f"✅ {len(df)} satır okundu")
    print(f"📊 {df['ref'].nunique()} benzersiz yevmiye fişi")
    return df

def prepare_move_data(df):
    """CSV verilerini ref'e göre grupla (her ref bir yevmiye fişi)"""
    moves_dict = defaultdict(list)

    for idx, row in df.iterrows():
        ref = str(row.get('ref', '')).strip()
        if not ref:
            continue

        # Partner VAT normalizasyonu
        partner_vat = str(row.get('partner_vat', '')).strip() if pd.notna(row.get('partner_vat')) else ''
        partner_vat = partner_vat.replace('.0', '') if partner_vat else ''

        moves_dict[ref].append({
            'date': str(row.get('date', '')).strip(),
            'journal_code': str(row.get('journal_code', '')).strip(),
            'account_code': str(row.get('account_code', '')).strip(),
            'account_name': str(row.get('account_name', '')).strip(),
            'partner_vat': partner_vat,
            'partner_name': str(row.get('partner_name', '')).strip() if pd.notna(row.get('partner_name')) else '',
            'label': str(row.get('label', '')).strip(),
            'debit': float(row.get('debit', 0)) if pd.notna(row.get('debit')) else 0.0,
            'credit': float(row.get('credit', 0)) if pd.notna(row.get('credit')) else 0.0,
            'invoice_ref': str(row.get('invoice_ref', '')).strip() if pd.notna(row.get('invoice_ref')) else '',
        })

    return moves_dict

def create_batch_script(batch_moves, batch_num, total_batches, *, post_moves: bool, create_missing_partners: bool):
    """Bir batch için Odoo shell script oluştur"""

    # Python dict olarak moves_data hazırla
    moves_data_str = "{\n"
    for ref, lines in batch_moves.items():
        moves_data_str += f"    '{ref}': [\n"
        for line in lines:
            moves_data_str += f"        {line},\n"
        moves_data_str += "    ],\n"
    moves_data_str += "}"

    script = f"""
import logging
import re
from decimal import Decimal, ROUND_HALF_UP
from difflib import SequenceMatcher
from odoo import Command
_logger = logging.getLogger(__name__)

print("="*60)
print(f"📦 BATCH {batch_num}/{total_batches} İŞLENİYOR")
print("="*60)

moves_data = {moves_data_str}
CREATE_MISSING_PARTNERS = {str(bool(create_missing_partners))}

created_count = 0
updated_count = 0
error_count = 0
skipped_count = 0

# --- Helpers ---
VAT_DIGITS_RE = re.compile(r"\\D+")

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

SUFFIX_RE = re.compile(r"\\b(A\\.?\\s*Ş\\.?|AS|A\\.?S\\.?|LTD\\.?|LTD\\s*Ş\\.?T\\.?İ\\.?|LİMİTED|Ş\\.?T\\.?İ\\.?|STI|TİC\\.?|SAN\\.?|VE|V\\.)\\b", re.IGNORECASE)
NON_ALNUM_RE = re.compile(r"[^0-9A-ZÇĞİÖŞÜ ]+", re.IGNORECASE)

TR_FOLD = str.maketrans("ÇĞİÖŞÜÂÊÎÔÛ", "CGIOSUAEIOU")

def normalize_name(raw):
    s = (raw or "").strip().upper()
    if not s:
        return ""
    s = NON_ALNUM_RE.sub(" ", s)
    s = SUFFIX_RE.sub(" ", s)
    s = " ".join(s.split())
    s = s.translate(TR_FOLD)
    return s

def tokenize(s: str):
    return [p for p in (s or "").split() if len(p) >= 3]

def token_containment_score(src: str, cand: str) -> float:
    # Candidate tokens are often a subset of Luca-abbreviated source name.
    ts = tokenize(src)
    tc = tokenize(cand)
    if not ts or not tc:
        return 0.0
    common = sum(1 for t in tc if t in ts)
    return common / max(1, len(tc))

def token_prefix_score(a: str, b: str) -> float:
    ta = tokenize(a)
    tb = tokenize(b)
    if not ta or not tb:
        return 0.0
    matched = 0
    for x in ta:
        for y in tb:
            if x.startswith(y) or y.startswith(x):
                matched += 1
                break
    return matched / max(1, len(ta))

def similarity(a, b):
    if not a or not b:
        return 0.0
    # Luca isimleri çoğu zaman kısaltma/fragment; prefix tabanlı skor daha güvenilir.
    seq = SequenceMatcher(None, a, b).ratio()
    pref = token_prefix_score(a, b)
    cont = token_containment_score(a, b)
    return max(seq, pref, cont)

def money(val):
    try:
        d = Decimal(str(val or "0"))
    except Exception:
        d = Decimal("0")
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

# Partner mapping (VAT -> Partner ID)
all_partner_vats = set()
all_partner_names = set()
for move_lines in moves_data.values():
    for line in move_lines:
        if line.get('partner_vat'):
            all_partner_vats.add(normalize_vat(line['partner_vat']))
        if line.get('partner_name'):
            all_partner_names.add(line['partner_name'])

partner_mapping = {{}}
odoo_partners = env['res.partner'].search([])
odoo_partner_rows = []
for p in odoo_partners:
    n = normalize_name(p.name)
    if not n:
        continue
    vat_norm = normalize_vat(p.vat)
    if vat_norm:
        partner_mapping[vat_norm] = p.id
        partner_mapping["TR" + vat_norm] = p.id
    odoo_partner_rows.append((p.id, vat_norm, n, p.name))

vat_hits = 0
if all_partner_vats:
    for v in all_partner_vats:
        if v and v in partner_mapping:
            vat_hits += 1
print(f"✅ VAT eşleştirme: {{vat_hits}}/{{len(all_partner_vats)}}")

# Fuzzy name mapping (only for names in this batch)
NAME_THRESHOLD = 0.80
NAME_THRESHOLD_SECONDARY = 0.70
name_to_partner_id = {{}}
if all_partner_names:
    for raw_name in sorted(all_partner_names):
        nn = normalize_name(raw_name)
        if not nn:
            continue
        best = (0.0, None)  # score, partner_id
        for pid, vat_norm, n_norm, orig in odoo_partner_rows:
            sc = similarity(nn, n_norm)
            if sc > best[0]:
                best = (sc, pid)
        if best[1] and best[0] >= NAME_THRESHOLD:
            name_to_partner_id[nn] = best[1]

print(f"✅ İsim eşleştirme (fuzzy): {{len(name_to_partner_id)}}/{{len(all_partner_names)}} (threshold={{NAME_THRESHOLD}})")

def pick_search_token(nn: str) -> str:
    parts = [p for p in nn.split() if len(p) >= 3]
    if not parts:
        return ""
    # Luca isimleri çoğu zaman kısaltma; ilk token genelde en ayırt edici (örn. ERUZUNLAR, DENSU, CEDIT, BIZIM).
    return parts[0]

def find_partner_id_by_name(raw_name: str):
    nn = normalize_name(raw_name)
    if not nn:
        return None
    if nn in name_to_partner_id:
        return name_to_partner_id[nn]

    token = pick_search_token(nn)
    if not token:
        return None

    candidates = env['res.partner'].search([('name', 'ilike', token)], limit=25)
    best = (0.0, None)
    for p in candidates:
        sc = similarity(nn, normalize_name(p.name))
        if sc > best[0]:
            best = (sc, p.id)
    if best[1] and best[0] >= NAME_THRESHOLD_SECONDARY:
        name_to_partner_id[nn] = best[1]
        return best[1]
    return None

def create_partner_for_line(line, require_prefix: str):
    name_raw = (line.get('partner_name') or '').strip()
    vat_raw = (line.get('partner_vat') or '').strip()
    if not name_raw and not vat_raw:
        return None
    vat_norm = normalize_vat(vat_raw)
    nn = normalize_name(name_raw)

    # Fast-path cache: use already-known mappings (preloaded + created/matched earlier in this batch)
    if vat_norm and vat_norm in partner_mapping:
        return partner_mapping[vat_norm]
    if nn and nn in name_to_partner_id:
        return name_to_partner_id[nn]

    # If VAT exists, try direct search again.
    if vat_norm:
        p = env['res.partner'].search([('vat', 'ilike', vat_norm)], limit=1)
        if p:
            partner_mapping[vat_norm] = p.id
            partner_mapping["TR" + vat_norm] = p.id
            if nn:
                name_to_partner_id[nn] = p.id
            return p.id

    # Try fuzzy name matching helper (updates name_to_partner_id cache internally)
    if name_raw:
        pid = find_partner_id_by_name(name_raw)
        if pid:
            if vat_norm:
                partner_mapping[vat_norm] = pid
                partner_mapping["TR" + vat_norm] = pid
            if nn:
                name_to_partner_id[nn] = pid
            return pid

    # Avoid duplicates: search by token and pick best similarity.
    token = pick_search_token(nn)
    candidates = env['res.partner'].search([('name', 'ilike', token)], limit=25) if token else env['res.partner'].search([], limit=25)
    best = (0.0, None)
    for p in candidates:
        sc = similarity(nn, normalize_name(p.name))
        if sc > best[0]:
            best = (sc, p.id)
    if best[1] and best[0] >= 0.65:
        if vat_norm:
            partner_mapping[vat_norm] = best[1]
            partner_mapping["TR" + vat_norm] = best[1]
        if nn:
            name_to_partner_id[nn] = best[1]
        return best[1]

    # Create new partner (minimal fields)
    vals = dict(name=name_raw)
    if vat_norm:
        vals['vat'] = vat_norm
    # Mark as customer/supplier based on account prefix
    if require_prefix == '120':
        vals['customer_rank'] = 1
    elif require_prefix == '320':
        vals['supplier_rank'] = 1
    p = env['res.partner'].create(vals)
    if vat_norm:
        partner_mapping[vat_norm] = p.id
        partner_mapping["TR" + vat_norm] = p.id
    if nn:
        name_to_partner_id[nn] = p.id
    return p.id

# Hesap mapping (hesap kodu -> Account)
all_account_codes = set()
for move_lines in moves_data.values():
    for line in move_lines:
        if line.get('account_code'):
            all_account_codes.add(line['account_code'])

account_mapping = {{}}
if all_account_codes:
    accounts = env['account.account'].search([('code', 'in', list(all_account_codes))])
    for account in accounts:
        account_mapping[account.code] = account

    missing_codes = sorted(set(all_account_codes) - set(account_mapping.keys()))
    if missing_codes:
        print(f"❌ Eksik hesap kodları (bu batch'te): {{len(missing_codes)}}")
        print("   " + ", ".join(missing_codes[:30]) + (" ..." if len(missing_codes) > 30 else ""))
        print("   Bu batch'te eksik hesap varsa ilgili fişler SKIP edilecek (hesap otomatik oluşturulmaz).")

    print(f"✅ {{len(account_mapping)}} hesap bulundu")

# Journal mapping
journal_codes = set()
for move_lines in moves_data.values():
    for line in move_lines:
        if line.get('journal_code'):
            journal_codes.add(line['journal_code'])

journal_mapping = {{}}
for code in journal_codes:
    journal = env['account.journal'].search([
        ('code', '=', code),
    ], limit=1)
    if journal:
        journal_mapping[code] = journal.id
    else:
        # Fallback: mevcut bir genel journal (tercihen MISC)
        fallback = env['account.journal'].search([('code', '=', 'MISC')], limit=1)
        if not fallback:
            fallback = env['account.journal'].search([('type', '=', 'general')], limit=1)
        if fallback:
            journal_mapping[code] = fallback.id
            print(f"⚠️ Journal code bulunamadı: {{code}} → fallback: {{fallback.code}}")
        else:
            print(f"❌ Journal bulunamadı ve fallback yok: {{code}} (fişler SKIP edilecek)")

print(f"✅ {{len(journal_mapping)}} journal hazır")

# Yevmiye fişlerini oluştur
for ref, move_lines in moves_data.items():
    try:
        # Bu ref'e sahip kayıt var mı kontrol et
        existing = env['account.move'].search([
            ('ref', '=', ref),
        ], limit=1)

        if existing:
            print(f"⏭️  Zaten var: {{ref}}")
            skipped_count += 1
            continue

        # İlk satırdan bilgileri al
        first_line = move_lines[0]
        date = first_line['date']
        journal_code = first_line['journal_code']

        if journal_code not in journal_mapping:
            print(f"❌ Journal bulunamadı: {{journal_code}} - {{ref}}")
            error_count += 1
            continue

        # Move lines hazırla
        line_vals = []
        total_debit = Decimal("0.00")
        total_credit = Decimal("0.00")

        for line in move_lines:
            account_code = line['account_code']
            account = account_mapping.get(account_code)
            if not account:
                print(f"❌ Hesap bulunamadı: {{account_code}} - {{ref}} (fiş SKIP)")
                error_count += 1
                line_vals = []
                break

            partner_id = None
            vat_norm = normalize_vat(line.get('partner_vat'))
            if vat_norm and vat_norm in partner_mapping:
                partner_id = partner_mapping[vat_norm]
            else:
                partner_id = find_partner_id_by_name(line.get('partner_name'))

            # Partner zorunluluğu (daraltılmış):
            # - 120/320 alt hesaplar tek hesap + partner yaklaşımıyla yönetiliyor; bu satırlarda partner şart.
            # - Diğer hesaplarda (örn. 360000/193000 gibi yanlış account_type/reconcile ayarı olabilen hesaplar)
            #   partner zorunluluğu uygulanmaz; aksi halde boş partner alanı yüzünden fişler bloklanır.
            require_partner = (account.code.startswith('120') or account.code.startswith('320'))
            if require_partner and not partner_id and CREATE_MISSING_PARTNERS:
                prefix = '120' if account.code.startswith('120') else '320'
                try:
                    partner_id = create_partner_for_line(line, prefix)
                    if partner_id:
                        print(f"➕ Partner oluşturuldu/eşlendi: ref={{ref}} account={{account.code}} partner_id={{partner_id}}")
                except Exception as e:
                    print("⚠️ Partner oluşturma hatası: ref=%s (%s)" % (ref, e))

            if require_partner and not partner_id:
                print(f"❌ Partner zorunlu ({{account.code}}) ama eşleşmedi: {{ref}} (VAT={{line.get('partner_vat','')}} NAME={{line.get('partner_name','')}})")
                error_count += 1
                line_vals = []
                break

            debit_d = money(line.get('debit', 0))
            credit_d = money(line.get('credit', 0))
            total_debit += debit_d
            total_credit += credit_d

            line_vals.append(Command.create({{
                'account_id': account.id,
                'partner_id': partner_id,
                'name': line['label'],
                'debit': float(debit_d),
                'credit': float(credit_d),
            }}))

        # Borç/alacak dengesi kontrolü
        if line_vals and (total_debit != total_credit):
            print(f"❌ Borç/Alacak dengesiz: {{ref}} ({{total_debit}} != {{total_credit}}) (fiş SKIP)")
            error_count += 1
            continue

        if not line_vals:
            skipped_count += 1
            continue

        # Move oluştur
        move_vals = {{
            'ref': ref,
            'date': date,
            'journal_id': journal_mapping[journal_code],
            'line_ids': line_vals,
        }}

        move = env['account.move'].create(move_vals)

        # Taslak (draft) olarak bırak; sadece istenirse post et
        if {str(bool(post_moves))}:
            try:
                move.action_post()
            except Exception as e:
                print(f"⚠️  Post edilemedi {{ref}}: {{str(e)}} (draft kaldı)")

        created_count += 1
        if created_count % 10 == 0:
            state = getattr(move, 'state', 'n/a')
            print(f"✅ {{created_count}} fiş oluşturuldu... (son: {{ref}}, state={{state}})")

    except Exception as e:
        print(f"❌ Hata {{ref}}: {{str(e)}}")
        error_count += 1
        continue

env.cr.commit()

print("="*60)
print(f"📊 BATCH {batch_num}/{total_batches} TAMAMLANDI")
print(f"   ✅ Oluşturulan: {{created_count}}")
print(f"   ⚠️  Güncellenen: {{updated_count}}")
print(f"   ⏭️  Atlanan: {{skipped_count}}")
print(f"   ❌ Hata: {{error_count}}")
print("="*60)
"""

    return script

def process_batch(batch_moves, batch_num, total_batches, *, post_moves: bool, create_missing_partners: bool):
    """Bir batch'i işle"""
    print(f"\n📦 Batch {batch_num}/{total_batches} hazırlanıyor ({len(batch_moves)} fiş)...")

    script = create_batch_script(batch_moves, batch_num, total_batches, post_moves=post_moves, create_missing_partners=create_missing_partners)
    script_file = f"/tmp/import_journal_2025_batch_{batch_num}.py"

    with open(script_file, 'w', encoding='utf-8') as f:
        f.write(script)

    print(f"🔧 Script hazır: {script_file}")
    print(f"🚀 Odoo shell ile çalıştırılıyor...")

    try:
        result = subprocess.run(
            ["docker", "exec", "-i", "joker-odoo", "odoo", "shell",
             "-d", DB_NAME, "--no-http", "-c", "/etc/odoo/odoo.conf"],
            input=script,
            text=True,
            capture_output=True,
            timeout=600  # 10 dakika timeout
        )

        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)

        if result.returncode != 0:
            print(f"❌ Batch {batch_num} başarısız!")
            return False

        return True

    except subprocess.TimeoutExpired:
        print(f"⏱️ Timeout! Batch {batch_num} 10 dakikada tamamlanamadı.")
        return False
    except Exception as e:
        print(f"❌ Hata: {e}")
        return False

def main():
    print("="*70)
    print("🎯 2025 YEVMİYE KAYITLARI YÜKLEME İŞLEMİ")
    print("="*70)

    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="0 ise tüm fişler; >0 ise ilk N fiş")
    parser.add_argument(
        "--refs-file",
        type=str,
        default="",
        help="Sadece bu dosyadaki ref'leri işle (satır başına 1 ref). Header 'ref' olabilir.",
    )
    parser.add_argument("--csv-file", type=str, default=CSV_FILE_DEFAULT, help="Prepared yevmiye CSV yolu")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--post", action="store_true", help="Fişleri posted olarak kaydet (varsayılan: draft)")
    parser.add_argument("--create-missing-partners", action="store_true", help="Eşleşmeyen 120/320 partnerlarını oluştur (varsayılan: kapalı)")
    args = parser.parse_args()

    # CSV oku
    df = load_journal_entries(args.csv_file)

    # Move'ları grupla
    moves_dict = prepare_move_data(df)
    print(f"\n📋 {len(moves_dict)} yevmiye fişi hazır")

    # Batch'lere böl
    all_refs = list(moves_dict.keys())
    if args.refs_file:
        try:
            with open(args.refs_file, "r", encoding="utf-8") as f:
                wanted = []
                for line in f.read().splitlines():
                    s = (line or "").strip()
                    if not s or s.lower() == "ref":
                        continue
                    wanted.append(s)
            wanted_set = set(wanted)
            all_refs = [r for r in all_refs if r in wanted_set]
            print(f"🎯 REFS-FILE aktif: {len(all_refs)} ref hedeflenecek ({args.refs_file})")
        except Exception as e:
            print(f"❌ refs-file okunamadı: {args.refs_file} ({e})")
            sys.exit(2)
    elif args.limit and args.limit > 0:
        all_refs = all_refs[: args.limit]
        print(f"🔎 LIMIT aktif: ilk {len(all_refs)} fiş işlenecek")

    total_batches = (len(all_refs) + args.batch_size - 1) // args.batch_size

    print(f"📦 {total_batches} batch'e bölündü (her batch {args.batch_size} fiş)")
    print(f"📝 Kayıt modu: {'POSTED' if args.post else 'DRAFT'}")

    # Her batch'i işle
    success_count = 0
    for i in range(total_batches):
        start_idx = i * args.batch_size
        end_idx = min((i + 1) * args.batch_size, len(all_refs))
        batch_refs = all_refs[start_idx:end_idx]

        batch_moves = {ref: moves_dict[ref] for ref in batch_refs}

        if process_batch(batch_moves, i + 1, total_batches, post_moves=args.post, create_missing_partners=args.create_missing_partners):
            success_count += 1
        else:
            print(f"\n⚠️  Batch {i + 1} başarısız, devam ediliyor...\n")

    print("\n" + "="*70)
    print("🎉 TAMAMLANDI!")
    print(f"   ✅ Başarılı batch: {success_count}/{total_batches}")
    print("="*70)

if __name__ == "__main__":
    main()
