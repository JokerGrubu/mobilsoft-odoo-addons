from odoo import models, fields, api, exceptions
import pandas as pd
import os
import logging
import math

_logger = logging.getLogger(__name__)

class JokerVeriMerkeziAktarim(models.Model):
    _name = 'joker.veri.merkezi'
    _description = 'Joker Veri Merkezi Aktarım Aracı'

    name = fields.Char(string='Aktarım Adı', default='Yeni Partner Aktarımı')
    dosya_yolu = fields.Char(string='Dosya Yolu', default='/joker/JOKER_VERI_MERKEZI/02_HAM_VERILER_VE_EXCEL/odoo_tum_partnerler_konsolide.csv')
    durum = fields.Selection([
        ('taslak', 'Taslak'),
        ('basladi', 'Aktarım Başladı'),
        ('tamamlandi', 'Tamamlandı'),
        ('hata', 'Hata Oluştu')
    ], string='Durum', default='taslak')
    
    islenen_kayit_sayisi = fields.Integer(string='İşlenen Kayıt Sayısı', default=0)
    olusturulan_kayit_sayisi = fields.Integer(string='Oluşturulan/Güncellenen Kayıt Sayısı', default=0)
    aktarim_logu = fields.Text(string='İşlem Logu')

    def action_aktarimi_baslat(self):
        for rec in self:
            rec.durum = 'basladi'
            rec.aktarim_logu = "Aktarım işlemi başlatıldı...\n"
            
            try:
                if not os.path.exists(rec.dosya_yolu):
                    raise exceptions.UserError(f"Dosya bulunamadı: {rec.dosya_yolu}")
                
                df = pd.read_csv(rec.dosya_yolu, dtype=str)
                df = df.fillna("")
                
                Partner = self.env['res.partner']
                
                # Öncelikle Ana Şirketleri Odoo'da aramak ve bulamadığında oluşturmak için
                # Bir sözlük tutacağız: {CSV_ID: Odoo_Record_ID}
                id_map = {}
                
                rec.islenen_kayit_sayisi = len(df)
                rec.aktarim_logu += f"Toplam {len(df)} kayıt okunuyor...\n"
                
                # 1. Faz: Ana Şirketleri / Parent'ı olmayanları Oluştur
                for index, row in df.iterrows():
                    parent_id_str = str(row.get('parent_id/id', ''))
                    
                    if not parent_id_str or parent_id_str == 'nan':
                        # VKN Kontrolü
                        vat = str(row.get('vat', '')).strip()
                        domain = []
                        if vat:
                            domain.append(('vat', '=', vat))
                        else:
                            domain.append(('name', '=', str(row.get('name', '')).strip()))
                            
                        mevcut_partner = Partner.search(domain, limit=1)
                        
                        vals = {
                            'name': str(row.get('name', '')).strip(),
                            'is_company': str(row.get('is_company', '')).lower() == 'true',
                            'vat': vat,
                            'ref': str(row.get('ref', '')),
                            'email': str(row.get('email', '')),
                            'phone': str(row.get('phone', '')),
                            'street': str(row.get('street', '')),
                            'city': str(row.get('city', '')),
                            'comment': str(row.get('comment', '')),
                            'active': True
                        }
                        
                        if mevcut_partner:
                            mevcut_partner.write(vals)
                            id_map[str(row.get('id', ''))] = mevcut_partner.id
                        else:
                            yeni_partner = Partner.create(vals)
                            id_map[str(row.get('id', ''))] = yeni_partner.id
                            rec.olusturulan_kayit_sayisi += 1
                
                rec.env.cr.commit() # Ana şirketleri veritabanına işle
                
                # 2. Faz: Şubeleri ve Kontkaları Bağla
                for index, row in df.iterrows():
                    parent_id_str = str(row.get('parent_id/id', ''))
                    
                    if parent_id_str and parent_id_str != 'nan':
                        # Ana şirketi haritadan bul
                        odoo_parent_id = id_map.get(parent_id_str)
                        
                        if odoo_parent_id:
                            # Aynı contact/delivery zaten var mı diye kontrol et (isime göre basit kontrol)
                            mevcut_sube = Partner.search([
                                ('parent_id', '=', odoo_parent_id),
                                ('name', '=', str(row.get('name', '')).strip()),
                                ('type', '=', str(row.get('type', 'contact')))
                            ], limit=1)
                            
                            vals = {
                                'name': str(row.get('name', '')).strip(),
                                'parent_id': odoo_parent_id,
                                'type': str(row.get('type', 'contact')),
                                'is_company': False,
                                'vat': str(row.get('vat', '')).strip(),
                                'email': str(row.get('email', '')),
                                'phone': str(row.get('phone', '')),
                                'street': str(row.get('street', '')),
                                'city': str(row.get('city', '')),
                                'active': True
                            }
                            
                            if mevcut_sube:
                                mevcut_sube.write(vals)
                            else:
                                Partner.create(vals)
                                rec.olusturulan_kayit_sayisi += 1

                rec.durum = 'tamamlandi'
                rec.aktarim_logu += "Aktarım başarıyla tamamlandı ve Odoo hiyerarşisi kuruldu.\n"
                
            except Exception as e:
                rec.durum = 'hata'
                rec.aktarim_logu += f"\nAktarım sırasında devasa bir hata oluştu:\n{str(e)}"
                _logger.error(f"Joker Veri Aktarım Hatası: {str(e)}")
