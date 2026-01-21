{
    'name': 'Türkiye İl/İlçe Verileri - MobilSoft',
    "summary": """İş Ortağında city(İlçe) için seçilebilir alanda Türkiye semt/ilçe bilgisini ekler""",
    "description": """Bu modül, Odoo'daki İş Ortağı kayıtlarında bulunan city (İlçe) alanı için
            Türkiye'ye özgü semt/ilçe seçeneklerini ekler ve seçilebilir hale getirir. Amaç,
            adres doğruluğunu artırmak ve Türkiye'ye özel adres girdilerini standardize etmektir.""",
    "version": "19.0.1.0.0",
    'license': 'LGPL-3',
    'author': 'MobilSoft',
    'maintainer': 'MobilSoft',
    "support": "destek@kitayazilim.com",
    'website': 'https://www.mobilsoft.net',
    "depends": ["base_address_extended", "contacts", "website"],
    "data": [
        "data/res.city.csv",
        "data/res_country_data.xml",
        "data/res_partner_data.xml",
    ],
    "images": [
        "static/description/main_screenshot.gif",
    ],
    "demo": [],
}
