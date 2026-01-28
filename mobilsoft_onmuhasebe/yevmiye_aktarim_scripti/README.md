# Yevmiye Aktarım Scripti

Bu klasör, Luca’dan alınan “Detay Fiş Listesi” gibi yevmiye kaynaklarını Odoo’ya **taslak (draft)** fiş olarak aktarmak için kullanılan splitter/aktarim araçlarını içerir.

> Amaç: Yevmiye fişlerini Odoo’ya **borç/alacak dengesi bozulmadan**, partner ve hesap eşleşmeleriyle birlikte, **kontrol edilebilir şekilde** (draft) almak.

## İçerik

- `transform_journal_xlsx.py`  
  Luca Excel (DETAY FİŞ LİSTESİ) dosyalarını parçalar/split eder ve Odoo import formatına uygun CSV üretir.

- `ensure_coa_required.py`  
  Yevmiye satırlarında geçen hesap kodlarının Odoo CoA’da varlığını garanti etmek için gereken hesapları oluşturur.

- `import_journal_2025.py`  
  Üretilen CSV’den Odoo’ya yevmiye fişlerini batch halinde yazar (varsayılan: draft). Gerekirse 120/320 satırlarında eksik partnerları oluşturabilir.

- `partner_cleanup.py`  
  VAT bazlı mükerrer partnerları ve “yakın zamanda otomatik oluşmuş isim mükerrerlerini” merge ederek temizlik yapar.

- `coa_required_from_2019_2025_journal.csv`  
  Joker ortamında tespit edilmiş gerekli hesap kodları listesi (örnek/başlangıç).

## Kullanım Akışı (Önerilen)

1) **Yedek al**
```
/joker/scripts/backup.sh
```

2) **Excel → Prepared CSV (split/transform)**
```
python3 transform_journal_xlsx.py --xlsx /joker/Mimar/sirket_verileri/Joker/2024.xlsx --out-dir /joker/Mimar/sirket_verileri/Prepared
```
Çıktılar örnek:
- `journal_2024_odoo_import.csv`
- `journal_2024_transform_summary.txt`

3) **Gerekli hesapları oluştur (CoA)**
```
python3 ensure_coa_required.py --execute
```

4) **Yevmiye fişlerini Odoo’ya aktar (draft)**
Tam yıl:
```
python3 import_journal_2025.py --csv-file /joker/Mimar/sirket_verileri/Prepared/journal_2024_odoo_import.csv
```

Sadece belirli ref listesi (ör. eksik fişleri tamamlama):
```
python3 import_journal_2025.py --csv-file /joker/Mimar/sirket_verileri/Prepared/journal_2024_odoo_import.csv --refs-file /joker/Mimar/sirket_verileri/Prepared/missing_refs_2024.csv
```

Partner oluşturma moduyla (120/320):
```
python3 import_journal_2025.py --csv-file /joker/Mimar/sirket_verileri/Prepared/journal_2024_odoo_import.csv --refs-file /joker/Mimar/sirket_verileri/Prepared/missing_refs_2024.csv --create-missing-partners
```

5) **Partner temizlik (merge)**
Dry-run:
```
python3 partner_cleanup.py
```
Uygula:
```
python3 partner_cleanup.py --execute
```

## Önemli Notlar

- Bu araçlar “yükle ve kontrol et” mantığı ile **draft** oluşturur; Patron onayı olmadan posted yapılması önerilmez.
- `import_journal_2025.py` Odoo’ya erişmek için `docker exec` ile Odoo shell kullanır; bu nedenle docker erişim izni gerekir.
- CSV kolonları iki formatta gelebilir:
  - Proje standardı: `date,ref,journal_code,account_code,partner_name,debit,credit,...`
  - Odoo import: `Date,Ref,Journal/Code,Account/Code,Partner,Debit,Credit,...`

