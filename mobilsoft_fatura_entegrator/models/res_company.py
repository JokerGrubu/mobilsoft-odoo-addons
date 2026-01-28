from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = 'res.company'

    fe_api_key = fields.Char(string='Fatura Entegratör API Key')
    fe_sale_channel_id = fields.Char(string='FE Satış Kanal ID', copy=False, readonly=True)
    fe_sale_channel_name = fields.Char(string='FE Satış Kanal Adı', copy=False, readonly=True)

    # Varsayılan Ayarlar
    fe_is_internet_sale = fields.Boolean(string='İnternet satışı mı?', default=False)
    fe_is_need_shipment = fields.Boolean(string='Teslimat gerekli mi?', default=False)
    fe_payment_method = fields.Selection(
        selection=[
            ('credit_or_debit', 'Banka/Kredi Kartı'),
            ('direct_transfer', 'EFT/Havale'),
            ('cash_on_delivery', 'Kapıda Ödeme'),
            ('payment_agent', 'Ödeme Aracısı'),
            ('other', 'Diğer'),
        ],
        string='Ödeme Yöntemi',
        default='credit_or_debit',
    )
    fe_payment_platform = fields.Char(string='Ödeme Aracı / Platform')
    fe_shipment_company_title = fields.Char(string='Kargo Firması')
    fe_shipment_company_tax_number = fields.Char(string='Firma Vergi No')
    fe_shipment_courier_name = fields.Char(string='Kurye Ad')
    fe_shipment_courier_tax_number = fields.Char(string='Kurye Vergi No')
    fe_exemption_code = fields.Selection(
        selection=[
            ('201', '17/1 Kültür ve Eğitim Amacı Taşıyan İşlemler'),
            ('202', '17/2-a Sağlık, Çevre Ve Sosyal Yardım Amaçlı İşlemler'),
            ('204', '17/2-c Yabancı Diplomatik Organ Ve Hayır Kurumlarının Yapacakları Bağışlarla İlgili Mal Ve Hizmet Alışları'),
            ('205', '17/2-d Taşınmaz Kültür Varlıklarına İlişkin Teslimler ve Mimarlık Hizmetleri'),
            ('206', '17/2-e Mesleki Kuruluşların İşlemleri'),
            ('207', '17/3 Askeri Fabrika, Tersane ve Atölyelerin İşlemleri'),
            ('208', '17/4-c Birleşme, Devir, Dönüşüm ve Bölünme İşlemleri'),
            ('209', '17/4-e Banka ve Sigorta Muameleleri Vergisi Kapsamına Giren İşlemler'),
            ('211', '17/4-h Zirai Amaçlı Su Teslimleri İle Köy Tüzel Kişiliklerince Yapılan İçme Suyu teslimleri'),
            ('212', '17/4-ı Serbest Bölgelerde Verilen Hizmetler'),
            ('213', '17/4-j Boru Hattı İle Yapılan Petrol Ve Gaz Taşımacılığı'),
            ('214', '17/4-k Organize Sanayi Bölgelerindeki Arsa ve İşyeri Teslimleri İle Konut Yapı'),
            ('215', '17/4-1 Varlık Yönetim Şirketlerinin İşlemleri'),
            ('216', '17/4-m Tasarruf Mevduatı Sigorta Fonunun İşlemleri'),
            ('217', '17/4-n Basın-Yayın ve Enformasyon Genel Müdürlüğüne Verilen Haber Hizmetleri'),
            ('218', 'KDV 17/4-o md. Gümrük Antrepoları, Geçici Depolama Yerleri ile Gümrüklü Sahalarda Vergisiz Satış Yapılan İşyeri, Depo ve Ardiye Gibi Bağımsız Birimlerin Kiralanması'),
            ('219', '17/4-p Hazine ve Arsa Ofisi Genel Müdürlüğünün işlemleri'),
            ('220', '17/4-r İki Tam Yıl Süreyle Sahip Olunan Taşınmaz ve İştirak Hisseleri ile 15/7/2023 tarihinden önce kurumların aktifinde kayıtlı Taşınmaz satışı'),
            ('221', 'Geçici 15 Konut Yapı Kooperatifleri, Belediyeler ve Sosyal Güvenlik Kuruluşlarına Verilen İnşaat Taahhüt Hizmeti'),
            ('223', 'Geçici 20/1 Teknoloji Geliştirme Bölgelerinde Yapılan İşlemler'),
            ('225', 'Geçici 23 Milli Eğitim Bakanlığına Yapılan Bilgisayar Bağışları İle İlgili Teslimler'),
            ('226', '17/2-b Özel Okulları, Üniversite ve Yüksekokullar Tarafından Verilen Bedelsiz Eğitim Ve Öğretim Hizmetleri'),
            ('227', '17/2-b Kanunların Gösterdiği Gerek Üzerine Bedelsiz Olarak Yapılan Teslim ve Hizmetler'),
            ('228', '17/2-b Kanunun (17/1) Maddesinde Sayılan Kurum ve Kuruluşlara Bedelsiz Olarak Yapılan Teslimler'),
            ('229', '17/2-b Gıda Bankacılığı Faaliyetinde Bulunan Dernek ve Vakıflara Bağışlanan Gıda, Temizlik, Giyecek ve Yakacak Maddeleri'),
            ('230', '17/4-g Külçe Altın, Külçe Gümüş Ve Kiymetli Taşlarin Teslimi'),
            ('231', '17/4-g Metal Plastik, Lastik, Kauçuk, Kağit, Cam Hurda Ve Atıkların Teslimi'),
            ('232', '17/4-g Döviz, Para, Damga Pulu, Değerli Kağıtlar, Hisse Senedi ve Tahvil Teslimleri'),
            ('234', '17/4-ş Konut Finansmanı Amacıyla Teminat Gösterilen ve İpotek Konulan Konutların Teslimi'),
            ('235', '16/1-c Transit ve Gümrük Antrepo Rejimleri İle Geçici Depolama ve Serbest Bölge Hükümlerinin Uygulandığı Malların Teslimi'),
            ('236', '19/2 Usulüne Göre Yürürlüğe Girmiş Uluslararası Anlaşmalar Kapsamındaki İstisnalar (İade Hakkı Tanınmayan)'),
            ('237', '17/4-t 5300 Sayılı Kanuna Göre Düzenlenen Ürün Senetlerinin İhtisas/Ticaret Borsaları Aracılığıyla İlk Teslimlerinden Sonraki Teslim'),
            ('238', '17/4-u Varlıkların Varlık Kiralama Şirketlerine Devri İle Bu Varlıkların Varlık Kiralama Şirketlerince Kiralanması ve Devralınan Kuruma Devri'),
            ('239', '17/4-y Taşınmazların Finansal Kiralama Şirketlerine Devri, Finansal Kiralama Şirketi Tarafından Devredene Kiralanması ve Devri'),
            ('240', '17/4-z Patentli Veya Faydalı Model Belgeli Buluşa İlişkin Gayri Maddi Hakların Kiralanması, Devri ve Satışı'),
            ('241', 'TürkAkım Gaz Boru Hattı Projesine İlişkin Anlaşmanın (9/b) Maddesinde Yer Alan Hizmetler'),
            ('242', 'KDV 17/4-ö md. Gümrük Antrepoları, Geçici Depolama Yerleri ile Gümrüklü Sahalarda, İthalat ve İhracat İşlemlerine konu mallar ile transit rejim kapsamında işlem gören mallar için verilen ardiye, depolama ve terminal hizmetleri'),
            ('301', '11/1-a Mal İhracatı (KDV)'),
            ('302', '11/1-a Hizmet İhracatı (KDV)'),
            ('303', '11/1-a Roaming Hizmetleri (KDV)'),
            ('304', '13/a Deniz Hava ve Demiryolu Taşıma Araçlarının Teslimi İle İnşa, Tadil, Bakım ve Onarımları (KDV)'),
            ('305', '13/b Deniz ve Hava Taşıma Araçları İçin Liman Ve Hava Meydanlarında Yapılan Hizmetler (KDV)'),
            ('306', '13/c Petrol Aramaları ve Petrol Boru Hatlarının İnşa ve Modernizasyonuna İlişkin Yapılan Teslim ve Hizmetler (KDV)'),
            ('307', '13/c Maden Arama, Altın, Gümüş ve Platin Madenleri İçin İşletme, Zenginleştirme Ve Rafinaj Faaliyetlerine İlişkin Teslim Ve Hizmetler[KDVGUT-(II/8-4)] (KDV)'),
            ('308', '13/d Teşvikli Yatırım Mallarının Teslimi (KDV)'),
            ('309', '13/e Liman Ve Hava Meydanlarının İnşası, Yenilenmesi Ve Genişletilmesi (KDV)'),
            ('310', '13/f Ulusal Güvenlik Amaçlı Teslim ve Hizmetler (KDV)'),
            ('311', '14/1 Uluslararası Taşımacılık (KDV)'),
            ('312', '15/a Diplomatik Organ Ve Misyonlara Yapılan Teslim ve Hizmetler (KDV)'),
            ('313', '15/b Uluslararası Kuruluşlara Yapılan Teslim ve Hizmetler (KDV)'),
            ('314', '19/2 Usulüne Göre Yürürlüğe Girmiş Uluslar Arası Anlaşmalar Kapsamındaki İstisnalar (KDV)'),
            ('315', '14/3 İhraç Konusu Eşyayı Taşıyan Kamyon, Çekici ve Yarı Romorklara Yapılan Motorin Teslimleri (KDV)'),
            ('316', '11/1-a Serbest Bölgelerdeki Müşteriler İçin Yapılan Fason Hizmetler (KDV)'),
            ('317', '17/4-s Engellilerin Eğitimleri, Meslekleri ve Günlük Yaşamlarına İlişkin Araç-Gereç ve Bilgisayar Programları (KDV)'),
            ('318', 'Geçici 29 3996 Sayılı Kanuna Göre Yap-İşlet-Devret Modeli Çerçevesinde Gerçekleştirilecek Projeler, 3359 Sayılı Kanuna Göre Kiralama Karşılığı Yaptırılan Sağlık Tesislerine İlişkin Projeler ve 652 Sayılı Kanun Hükmünde Kararnameye Göre Kiralama Karşılığı Yaptırılan Eğitim Öğretim Tesislerine İlişkin Projelere İlişkin Teslim ve Hizmetler (KDV)'),
            ('319', '13/g Başbakanlık Merkez Teşkilatına Yapılan Araç Teslimleri (KDV)'),
            ('320', 'Geçici 16 (6111 sayılı K.) İSMEP Kapsamında İstanbul İl Özel İdaresi\'ne Bağlı Olarak Faaliyet Gösteren "İstanbul Proje Koordinasyon Birimi"ne Yapılacak Teslim ve Hizmetler (KDV)'),
            ('321', 'Geçici 26 Birleşmiş Milletler (BM) ile Kuzey Atlantik Antlaşması Teşkilatı (NATO) Temsilcilikleri ve Bu Teşkilatlara Bağlı Program, Fon ve Özel İhtisas Kuruluşları ile İktisadi İşbirliği ve Kalkınma Teşkilatına (OECD) Resmi Kullanımları İçin Yapılacak Mal Teslimi ve Hizmet İfaları, Bunların Sosyal ve Ekonomik Yardım Amacıyla Bedelsiz Olarak Yapacakları Mal Teslimi ve Hizmet İfaları İle İlgili Bunlara Yapılan Mal Teslimi ve Hizmet İfaları (KDV)'),
            ('322', '11/1-a Türkiye\'de İkamet Etmeyenlere Özel Fatura ile Yapılan Teslimler (Bavul Ticareti) (KDV)'),
            ('323', '13/ğ 5300 Sayılı Kanuna Göre Düzenlenen Ürün Senetlerinin İhtisas/Ticaret Borsaları Aracılığıyla İlk Teslimi (KDV)'),
            ('324', '13/h Türkiye Kızılay Derneğine Yapılan Teslim ve Hizmetler ile Türkiye Kızılay Derneğinin Teslim ve Hizmetleri (KDV)'),
            ('325', '13/ı Yem Teslimleri (KDV)'),
            ('326', '13/ı Gıda, Tarım ve Hayvancılık Bakanlığı Tarafından Tescil Edilmiş Gübrelerin Teslimi (KDV)'),
            ('327', '13/ı Gıda, Tarım ve Hayvancılık Bakanlığı Tarafından Tescil Edilmiş Gübrelerin İçeriğinde Bulunan Hammaddelerin Gübre Üreticilerine Teslimi (KDV)'),
            ('328', '13/i Konut veya İşyeri Teslimleri (KDV)'),
            ('329', 'Eğitimde Fırsatları Artırma ve Teknolojiyi İyileştirme Hareketi (FATİH) projesi Kapsamında Milli Eğitim Bakanlığına Yapılacak Mal Teslimi ve Hizmet İfası (KDV)'),
            ('330', 'KDV 13/j md. Organize Sanayi Bölgeleri ile Küçük Sanayi Sitelerinin İnşasına İlişkin Teslim ve Hizmetler (KDV)'),
            ('331', 'KDV 13/m md. Ar-Ge, Yenilik ve Tasarım Faaliyetlerinde Kullanılmak Üzere Yapılan Yeni Makina ve Teçhizat Teslimlerinde İstisna (KDV)'),
            ('332', 'KDV Geçici 39. Md. İmalat Sanayiinde Kullanılmak Üzere Yapılan Yeni Makina ve Teçhizat Teslimlerinde İstisna (KDV)'),
            ('333', 'KDV 13/k md. Kapsamında Genel ve Özel Bütçeli Kamu İdarelerine, İl Özel İdarelerine, Belediyelere ve Köylere bağışlanan Tesislerin İnşasına İlişkin İstisna (KDV)'),
            ('334', 'KDV 13/l md. Kapsamında Yabancılara Verilen Sağlık Hizmetlerinde İstisna (KDV)'),
            ('335', 'KDV 13/n Basılı Kitap ve Süreli Yayınların Teslimleri (KDV)'),
            ('336', 'Geçici 40 UEFA Müsabakaları Kapsamında Yapılacak Teslim ve Hizmetler (KDV)'),
            ('337', 'Türk Akım Gaz Boru Hattı Projesine İlişkin Anlaşmanın (9/h) Maddesi Kapsamındaki Gaz Taşıma Hizmetleri (KDV)'),
            ('338', 'İmalatçıların Mal İhracatları (KDV)'),
            ('339', 'İmalat Sanayii ile Turizme Yönelik Yatırım Teşvik Belgesi Kapsamındaki İnşaat İşlerine İlişkin Teslim ve Hizmetler (KDV)'),
            ('340', 'Elektrik Motorlu Taşıt Araçlarının Geliştirilmesine Yönelik Mühendislik Hizmetleri (KDV)'),
            ('341', 'Afetzedelere Bağışlanacak Konutların İnşasına İlişkin İstisna (KDV)'),
            ('342', 'Genel Bütçeli Kamu İdarelerine Bağışlanacak Taşınmazların İnşasına İlişkin İstisna (KDV)'),
            ('343', 'Genel Bütçeli Kamu İdarelerine Bağışlanacak Konutların Yabancı Devlet Kurum ve Kuruluşlarına Teslimine İlişkin İstisna (KDV)'),
            ('101', 'İhracat İstisnası (ÖTV)'),
            ('102', 'Diplomatik İstisna (ÖTV)'),
            ('103', 'Askeri Amaçlı İstisna (ÖTV)'),
            ('104', 'Petrol Arama Faaliyetlerinde Bulunanlara Yapılan Teslimler (ÖTV)'),
            ('105', 'Uluslararası Anlaşmadan Doğan İstisna (ÖTV)'),
            ('106', 'Diğer İstisnalar (ÖTV)'),
            ('107', '7/a Maddesi Kapsamında Yapılan Teslimler (ÖTV)'),
            ('108', 'Geçici 5. Madde Kapsamında Yapılan Teslimler (ÖTV)'),
        ],
        string='Varsayılan Muafiyet Kodu',
    )
    fe_exemption_reason = fields.Char(string='Vergi Muafiyet Sebebi', compute='_compute_exemption_reason', store=False, readonly=True)
    fe_description = fields.Text(string='Açıklama')

    @api.depends('fe_exemption_code')
    def _compute_exemption_reason(self):
        """Exemption code'a göre exemption reason'ı hesapla"""
        exemption_aliases = {
            '201': '17/1 Kültür ve Eğitim Amacı Taşıyan İşlemler',
            '202': '17/2-a Sağlık, Çevre Ve Sosyal Yardım Amaçlı İşlemler',
            '204': '17/2-c Yabancı Diplomatik Organ Ve Hayır Kurumlarının Yapacakları Bağışlarla İlgili Mal Ve Hizmet Alışları',
            '205': '17/2-d Taşınmaz Kültür Varlıklarına İlişkin Teslimler ve Mimarlık Hizmetleri',
            '206': '17/2-e Mesleki Kuruluşların İşlemleri',
            '207': '17/3 Askeri Fabrika, Tersane ve Atölyelerin İşlemleri',
            '208': '17/4-c Birleşme, Devir, Dönüşüm ve Bölünme İşlemleri',
            '209': '17/4-e Banka ve Sigorta Muameleleri Vergisi Kapsamına Giren İşlemler',
            '211': '17/4-h Zirai Amaçlı Su Teslimleri İle Köy Tüzel Kişiliklerince Yapılan İçme Suyu teslimleri',
            '212': '17/4-ı Serbest Bölgelerde Verilen Hizmetler',
            '213': '17/4-j Boru Hattı İle Yapılan Petrol Ve Gaz Taşımacılığı',
            '214': '17/4-k Organize Sanayi Bölgelerindeki Arsa ve İşyeri Teslimleri İle Konut Yapı',
            '215': '17/4-1 Varlık Yönetim Şirketlerinin İşlemleri',
            '216': '17/4-m Tasarruf Mevduatı Sigorta Fonunun İşlemleri',
            '217': '17/4-n Basın-Yayın ve Enformasyon Genel Müdürlüğüne Verilen Haber Hizmetleri',
            '218': 'KDV 17/4-o md. Gümrük Antrepoları, Geçici Depolama Yerleri ile Gümrüklü Sahalarda Vergisiz Satış Yapılan İşyeri, Depo ve Ardiye Gibi Bağımsız Birimlerin Kiralanması',
            '219': '17/4-p Hazine ve Arsa Ofisi Genel Müdürlüğünün işlemleri',
            '220': '17/4-r İki Tam Yıl Süreyle Sahip Olunan Taşınmaz ve İştirak Hisseleri ile 15/7/2023 tarihinden önce kurumların aktifinde kayıtlı Taşınmaz satışı',
            '221': 'Geçici 15 Konut Yapı Kooperatifleri, Belediyeler ve Sosyal Güvenlik Kuruluşlarına Verilen İnşaat Taahhüt Hizmeti',
            '223': 'Geçici 20/1 Teknoloji Geliştirme Bölgelerinde Yapılan İşlemler',
            '225': 'Geçici 23 Milli Eğitim Bakanlığına Yapılan Bilgisayar Bağışları İle İlgili Teslimler',
            '226': '17/2-b Özel Okulları, Üniversite ve Yüksekokullar Tarafından Verilen Bedelsiz Eğitim Ve Öğretim Hizmetleri',
            '227': '17/2-b Kanunların Gösterdiği Gerek Üzerine Bedelsiz Olarak Yapılan Teslim ve Hizmetler',
            '228': '17/2-b Kanunun (17/1) Maddesinde Sayılan Kurum ve Kuruluşlara Bedelsiz Olarak Yapılan Teslimler',
            '229': '17/2-b Gıda Bankacılığı Faaliyetinde Bulunan Dernek ve Vakıflara Bağışlanan Gıda, Temizlik, Giyecek ve Yakacak Maddeleri',
            '230': '17/4-g Külçe Altın, Külçe Gümüş Ve Kiymetli Taşlarin Teslimi',
            '231': '17/4-g Metal Plastik, Lastik, Kauçuk, Kağit, Cam Hurda Ve Atıkların Teslimi',
            '232': '17/4-g Döviz, Para, Damga Pulu, Değerli Kağıtlar, Hisse Senedi ve Tahvil Teslimleri',
            '234': '17/4-ş Konut Finansmanı Amacıyla Teminat Gösterilen ve İpotek Konulan Konutların Teslimi',
            '235': '16/1-c Transit ve Gümrük Antrepo Rejimleri İle Geçici Depolama ve Serbest Bölge Hükümlerinin Uygulandığı Malların Teslimi',
            '236': '19/2 Usulüne Göre Yürürlüğe Girmiş Uluslararası Anlaşmalar Kapsamındaki İstisnalar (İade Hakkı Tanınmayan)',
            '237': '17/4-t 5300 Sayılı Kanuna Göre Düzenlenen Ürün Senetlerinin İhtisas/Ticaret Borsaları Aracılığıyla İlk Teslimlerinden Sonraki Teslim',
            '238': '17/4-u Varlıkların Varlık Kiralama Şirketlerine Devri İle Bu Varlıkların Varlık Kiralama Şirketlerince Kiralanması ve Devralınan Kuruma Devri',
            '239': '17/4-y Taşınmazların Finansal Kiralama Şirketlerine Devri, Finansal Kiralama Şirketi Tarafından Devredene Kiralanması ve Devri',
            '240': '17/4-z Patentli Veya Faydalı Model Belgeli Buluşa İlişkin Gayri Maddi Hakların Kiralanması, Devri ve Satışı',
            '241': 'TürkAkım Gaz Boru Hattı Projesine İlişkin Anlaşmanın (9/b) Maddesinde Yer Alan Hizmetler',
            '242': 'KDV 17/4-ö md. Gümrük Antrepoları, Geçici Depolama Yerleri ile Gümrüklü Sahalarda, İthalat ve İhracat İşlemlerine konu mallar ile transit rejim kapsamında işlem gören mallar için verilen ardiye, depolama ve terminal hizmetleri',
            '301': '11/1-a Mal İhracatı (KDV)',
            '302': '11/1-a Hizmet İhracatı (KDV)',
            '303': '11/1-a Roaming Hizmetleri (KDV)',
            '304': '13/a Deniz Hava ve Demiryolu Taşıma Araçlarının Teslimi İle İnşa, Tadil, Bakım ve Onarımları (KDV)',
            '305': '13/b Deniz ve Hava Taşıma Araçları İçin Liman Ve Hava Meydanlarında Yapılan Hizmetler (KDV)',
            '306': '13/c Petrol Aramaları ve Petrol Boru Hatlarının İnşa ve Modernizasyonuna İlişkin Yapılan Teslim ve Hizmetler (KDV)',
            '307': '13/c Maden Arama, Altın, Gümüş ve Platin Madenleri İçin İşletme, Zenginleştirme Ve Rafinaj Faaliyetlerine İlişkin Teslim Ve Hizmetler[KDVGUT-(II/8-4)] (KDV)',
            '308': '13/d Teşvikli Yatırım Mallarının Teslimi (KDV)',
            '309': '13/e Liman Ve Hava Meydanlarının İnşası, Yenilenmesi Ve Genişletilmesi (KDV)',
            '310': '13/f Ulusal Güvenlik Amaçlı Teslim ve Hizmetler (KDV)',
            '311': '14/1 Uluslararası Taşımacılık (KDV)',
            '312': '15/a Diplomatik Organ Ve Misyonlara Yapılan Teslim ve Hizmetler (KDV)',
            '313': '15/b Uluslararası Kuruluşlara Yapılan Teslim ve Hizmetler (KDV)',
            '314': '19/2 Usulüne Göre Yürürlüğe Girmiş Uluslar Arası Anlaşmalar Kapsamındaki İstisnalar (KDV)',
            '315': '14/3 İhraç Konusu Eşyayı Taşıyan Kamyon, Çekici ve Yarı Romorklara Yapılan Motorin Teslimleri (KDV)',
            '316': '11/1-a Serbest Bölgelerdeki Müşteriler İçin Yapılan Fason Hizmetler (KDV)',
            '317': '17/4-s Engellilerin Eğitimleri, Meslekleri ve Günlük Yaşamlarına İlişkin Araç-Gereç ve Bilgisayar Programları (KDV)',
            '318': 'Geçici 29 3996 Sayılı Kanuna Göre Yap-İşlet-Devret Modeli Çerçevesinde Gerçekleştirilecek Projeler, 3359 Sayılı Kanuna Göre Kiralama Karşılığı Yaptırılan Sağlık Tesislerine İlişkin Projeler ve 652 Sayılı Kanun Hükmünde Kararnameye Göre Kiralama Karşılığı Yaptırılan Eğitim Öğretim Tesislerine İlişkin Projelere İlişkin Teslim ve Hizmetler (KDV)',
            '319': '13/g Başbakanlık Merkez Teşkilatına Yapılan Araç Teslimleri (KDV)',
            '320': 'Geçici 16 (6111 sayılı K.) İSMEP Kapsamında İstanbul İl Özel İdaresi\'ne Bağlı Olarak Faaliyet Gösteren "İstanbul Proje Koordinasyon Birimi"ne Yapılacak Teslim ve Hizmetler (KDV)',
            '321': 'Geçici 26 Birleşmiş Milletler (BM) ile Kuzey Atlantik Antlaşması Teşkilatı (NATO) Temsilcilikleri ve Bu Teşkilatlara Bağlı Program, Fon ve Özel İhtisas Kuruluşları ile İktisadi İşbirliği ve Kalkınma Teşkilatına (OECD) Resmi Kullanımları İçin Yapılacak Mal Teslimi ve Hizmet İfaları, Bunların Sosyal ve Ekonomik Yardım Amacıyla Bedelsiz Olarak Yapacakları Mal Teslimi ve Hizmet İfaları İle İlgili Bunlara Yapılan Mal Teslimi ve Hizmet İfaları (KDV)',
            '322': '11/1-a Türkiye\'de İkamet Etmeyenlere Özel Fatura ile Yapılan Teslimler (Bavul Ticareti) (KDV)',
            '323': '13/ğ 5300 Sayılı Kanuna Göre Düzenlenen Ürün Senetlerinin İhtisas/Ticaret Borsaları Aracılığıyla İlk Teslimi (KDV)',
            '324': '13/h Türkiye Kızılay Derneğine Yapılan Teslim ve Hizmetler ile Türkiye Kızılay Derneğinin Teslim ve Hizmetleri (KDV)',
            '325': '13/ı Yem Teslimleri (KDV)',
            '326': '13/ı Gıda, Tarım ve Hayvancılık Bakanlığı Tarafından Tescil Edilmiş Gübrelerin Teslimi (KDV)',
            '327': '13/ı Gıda, Tarım ve Hayvancılık Bakanlığı Tarafından Tescil Edilmiş Gübrelerin İçeriğinde Bulunan Hammaddelerin Gübre Üreticilerine Teslimi (KDV)',
            '328': '13/i Konut veya İşyeri Teslimleri (KDV)',
            '329': 'Eğitimde Fırsatları Artırma ve Teknolojiyi İyileştirme Hareketi (FATİH) projesi Kapsamında Milli Eğitim Bakanlığına Yapılacak Mal Teslimi ve Hizmet İfası (KDV)',
            '330': 'KDV 13/j md. Organize Sanayi Bölgeleri ile Küçük Sanayi Sitelerinin İnşasına İlişkin Teslim ve Hizmetler (KDV)',
            '331': 'KDV 13/m md. Ar-Ge, Yenilik ve Tasarım Faaliyetlerinde Kullanılmak Üzere Yapılan Yeni Makina ve Teçhizat Teslimlerinde İstisna (KDV)',
            '332': 'KDV Geçici 39. Md. İmalat Sanayiinde Kullanılmak Üzere Yapılan Yeni Makina ve Teçhizat Teslimlerinde İstisna (KDV)',
            '333': 'KDV 13/k md. Kapsamında Genel ve Özel Bütçeli Kamu İdarelerine, İl Özel İdarelerine, Belediyelere ve Köylere bağışlanan Tesislerin İnşasına İlişkin İstisna (KDV)',
            '334': 'KDV 13/l md. Kapsamında Yabancılara Verilen Sağlık Hizmetlerinde İstisna (KDV)',
            '335': 'KDV 13/n Basılı Kitap ve Süreli Yayınların Teslimleri (KDV)',
            '336': 'Geçici 40 UEFA Müsabakaları Kapsamında Yapılacak Teslim ve Hizmetler (KDV)',
            '337': 'Türk Akım Gaz Boru Hattı Projesine İlişkin Anlaşmanın (9/h) Maddesi Kapsamındaki Gaz Taşıma Hizmetleri (KDV)',
            '338': 'İmalatçıların Mal İhracatları (KDV)',
            '339': 'İmalat Sanayii ile Turizme Yönelik Yatırım Teşvik Belgesi Kapsamındaki İnşaat İşlerine İlişkin Teslim ve Hizmetler (KDV)',
            '340': 'Elektrik Motorlu Taşıt Araçlarının Geliştirilmesine Yönelik Mühendislik Hizmetleri (KDV)',
            '341': 'Afetzedelere Bağışlanacak Konutların İnşasına İlişkin İstisna (KDV)',
            '342': 'Genel Bütçeli Kamu İdarelerine Bağışlanacak Taşınmazların İnşasına İlişkin İstisna (KDV)',
            '343': 'Genel Bütçeli Kamu İdarelerine Bağışlanacak Konutların Yabancı Devlet Kurum ve Kuruluşlarına Teslimine İlişkin İstisna (KDV)',
            '101': 'İhracat İstisnası (ÖTV)',
            '102': 'Diplomatik İstisna (ÖTV)',
            '103': 'Askeri Amaçlı İstisna (ÖTV)',
            '104': 'Petrol Arama Faaliyetlerinde Bulunanlara Yapılan Teslimler (ÖTV)',
            '105': 'Uluslararası Anlaşmadan Doğan İstisna (ÖTV)',
            '106': 'Diğer İstisnalar (ÖTV)',
            '107': '7/a Maddesi Kapsamında Yapılan Teslimler (ÖTV)',
            '108': 'Geçici 5. Madde Kapsamında Yapılan Teslimler (ÖTV)',
        }
        for record in self:
            if record.fe_exemption_code:
                record.fe_exemption_reason = exemption_aliases.get(record.fe_exemption_code, '')
            else:
                record.fe_exemption_reason = ''

    def fe_get_client(self):
        self.ensure_one()
        return self.env['fe.client'].with_company(self.id)

    def _fe_create_sale_channel_if_needed(self):
        for company in self:
            if company.fe_api_key and not company.fe_sale_channel_id:
                client = company.fe_get_client()
                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
                payload = {
                    'sale_channel': 'wordpress',
                    'settings': {
                        'domain': base_url,
                    },
                }
                sc = client.integration_sale_channel_create(payload)
                sc_data = sc.get('data') or sc
                sc_id = sc_data.get('id')
                sc_name = sc_data.get('name') or 'WordPress'
                if sc_id:
                    company.write({'fe_sale_channel_id': sc_id, 'fe_sale_channel_name': sc_name})
                    company.message_post(body=_('FE Satış Kanalı oluşturuldu: %s') % sc_name)

    def fe_connect(self):
        self._fe_create_sale_channel_if_needed()
        return True

    def fe_disconnect(self):
        for company in self:
            if company.fe_sale_channel_id:
                client = company.fe_get_client()
                try:
                    client.integration_sale_channel_destroy(company.fe_sale_channel_id)
                except Exception:  # noqa: BLE001
                    # Sunucu tarafında zaten kaldırılmış olabilir; yine de temizle.
                    pass
            company.write({'fe_sale_channel_id': False, 'fe_sale_channel_name': False, 'fe_api_key': False})
            company.message_post(body=_('FE bağlantısı kesildi ve API anahtarı temizlendi.'))
        return True

    def write(self, vals):
        res = super().write(vals)
        # Kaydet sonrası otomatik bağlantı kurulumu / temizliği
        for company in self:
            if 'fe_api_key' in vals:
                if vals.get('fe_api_key'):
                    company._fe_create_sale_channel_if_needed()
                else:
                    # API anahtarı temizlenmişse, varsa satış kanalını da kaldır
                    if company.fe_sale_channel_id:
                        try:
                            client = company.fe_get_client()
                            client.integration_sale_channel_destroy(company.fe_sale_channel_id)
                        except Exception:  # noqa: BLE001
                            pass
                        super(ResCompany, company).write({'fe_sale_channel_id': False, 'fe_sale_channel_name': False})
        return res

