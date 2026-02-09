# -*- coding: utf-8 -*-
"""
QNB e-Solutions API Client
SOAP tabanlı web servisi ile iletişim
"""

import base64
import hashlib
import logging
import uuid
from datetime import date, datetime, timedelta
from io import BytesIO
import zipfile

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

try:
    from zeep import Client, Settings
    from zeep.wsse.username import UsernameToken
    from zeep.transports import Transport
    from zeep.plugins import HistoryPlugin
    from requests import Session
    ZEEP_INSTALLED = True
except ImportError:
    ZEEP_INSTALLED = False
    _logger.warning("zeep library not installed. Please install: pip install zeep")

try:
    from lxml import etree
    LXML_INSTALLED = True
except ImportError:
    LXML_INSTALLED = False
    _logger.warning("lxml library not installed. Please install: pip install lxml")


class QnbApiClient(models.AbstractModel):
    """QNB e-Solutions API İstemcisi"""
    _name = 'qnb.api.client'
    _description = 'QNB e-Solutions API Client'

    # WSDL Endpoints - QNB e-Solutions
    # Test ortamları (Gönderici/Alıcı test için)
    WSDL_TEST1 = 'https://erpefaturatest1.qnbesolutions.com.tr/efatura/ws/connectorService?wsdl'
    WSDL_TEST2 = 'https://erpefaturatest2.qnbesolutions.com.tr/efatura/ws/connectorService?wsdl'
    # Canlı ortam - QNB eFinans
    WSDL_PROD = 'https://connector.qnbefinans.com/connector/ws/connectorService?wsdl'

    # User Service WSDL (kullanıcı sorgulamaları için)
    USER_WSDL_TEST1 = 'https://erpefaturatest1.qnbesolutions.com.tr/efatura/ws/userService?wsdl'
    USER_WSDL_TEST2 = 'https://erpefaturatest2.qnbesolutions.com.tr/efatura/ws/userService?wsdl'

    def _get_wsdl_url(self, company=None):
        """WSDL URL'sini döndür"""
        if not company:
            company = self.env.company

        if company.qnb_environment == 'test':
            # Şirket ayarlarından özel URL varsa onu kullan
            if hasattr(company, 'qnb_wsdl_url') and company.qnb_wsdl_url:
                return company.qnb_wsdl_url
            return self.WSDL_TEST1  # Varsayılan test1 ortamı
        return self.WSDL_PROD

    def _get_client(self, company=None):
        """SOAP Client oluştur"""
        if not ZEEP_INSTALLED:
            raise UserError(_("zeep kütüphanesi kurulu değil. Lütfen 'pip install zeep' komutunu çalıştırın."))

        if not company:
            company = self.env.company

        if not company.qnb_username or not company.qnb_password:
            raise UserError(_("QNB e-Solutions API kullanıcı bilgileri tanımlanmamış. Ayarlar menüsünden yapılandırın."))

        wsdl_url = self._get_wsdl_url(company)

        # Session ve Transport ayarları
        session = Session()
        session.verify = True
        transport = Transport(session=session, timeout=60)

        # WSSE Username Token (QNB için use_digest=False gerekli)
        wsse = UsernameToken(
            username=company.qnb_username,
            password=company.qnb_password,
            use_digest=False
        )

        # Zeep ayarları
        settings = Settings(strict=False, xml_huge_tree=True)

        # History plugin (debug için)
        history = HistoryPlugin()

        try:
            client = Client(
                wsdl=wsdl_url,
                wsse=wsse,
                transport=transport,
                settings=settings,
                plugins=[history]
            )
            return client, history
        except Exception as e:
            _logger.error(f"QNB API bağlantı hatası: {str(e)}")
            raise UserError(_("QNB e-Solutions'a bağlanılamadı: %s") % str(e))

    def _generate_uuid(self):
        """UUID oluştur"""
        return str(uuid.uuid4())

    def _generate_document_hash(self, content):
        """Belge hash değeri oluştur"""
        if isinstance(content, str):
            content = content.encode('utf-8')
        return hashlib.md5(content).hexdigest()

    def _get_company_vkn(self, company=None):
        """Şirket VKN bilgisini normalize ederek döndür (sadece rakamlar).

        QNB API için 10 haneli VKN gerekir. TCKN (11 hane) ile çalışmaz.
        Öncelik: qnb_username > vat (sadece 10 hane ise)
        """
        if not company:
            company = self.env.company

        # Önce qnb_username'den VKN çıkar (genelde "VKN.ws" formatında)
        if company.qnb_username:
            vkn_from_username = ''.join(filter(str.isdigit, str(company.qnb_username)))
            if len(vkn_from_username) == 10:
                return vkn_from_username

        # Sonra vat'tan dene (sadece 10 hane ise - VKN)
        if company.vat:
            vkn_from_vat = ''.join(filter(str.isdigit, str(company.vat)))
            if len(vkn_from_vat) == 10:
                return vkn_from_vat

        # Hiçbiri uygun değilse qnb_username'den ne varsa döndür
        if company.qnb_username:
            return ''.join(filter(str.isdigit, str(company.qnb_username)))

        return ''

    def _parse_qnb_date(self, value):
        """QNB'den gelen tarihleri date'e çevir (YYYYMMDD, YYYY-MM-DD, DD.MM.YYYY destekler)."""
        if not value:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value

        s = str(value).strip()
        if not s:
            return None
        if len(s) == 8 and s.isdigit():
            return datetime.strptime(s, '%Y%m%d').date()
        for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y'):
            try:
                return datetime.strptime(s, fmt).date()
            except Exception:
                continue
        return None

    def test_connection(self, company=None):
        """
        QNB e-Solutions bağlantı testi
        WSDL'e bağlanıp kullanılabilir metodları kontrol et
        """
        try:
            client, history = self._get_client(company)

            # WSDL başarıyla yüklendiyse bağlantı başarılı
            services = list(client.wsdl.services.keys())
            operations = []

            for service in client.wsdl.services.values():
                for port in service.ports.values():
                    operations.extend(list(port.binding._operations.keys()))

            # Temel işlevler kontrol et
            required_ops = [
                'belgeGonderExt',
                'gidenBelgeDurumSorgula',
            ]
            user_ops = [
                'kayitliKullaniciListele',
                'kayitliKullaniciListeleExtended',
            ]

            missing_ops = [op for op in required_ops if op not in operations]
            has_user_op = any(op in operations for op in user_ops)

            result = {
                'success': True,
                'message': '✅ QNB e-Solutions bağlantısı başarılı',
                'wsdl_url': self._get_wsdl_url(company),
                'services': services,
                'total_operations': len(operations),
                'available_operations': sorted(operations),
                'required_operations_found': not missing_ops and has_user_op
            }

            if missing_ops:
                result['warning'] = f'⚠️ Gerekli metodlardan {len(missing_ops)} tanesinden biri eksik: {", ".join(missing_ops)}'
            if not has_user_op:
                result['warning'] = (result.get('warning', '') + ' ⚠️ Kayıtlı kullanıcı sorgulama metodu bulunamadı.').strip()

            return result

        except Exception as e:
            _logger.error(f"QNB bağlantı testi hatası: {str(e)}")
            return {
                'success': False,
                'message': f'❌ Bağlantı hatası: {str(e)[:200]}'
            }

    # ============================================
    # KAYITLI KULLANICI İŞLEMLERİ
    # ============================================

    def check_registered_user(self, vkn_tckn, company=None):
        """
        GİB'e kayıtlı e-Fatura kullanıcısı kontrolü
        :param vkn_tckn: VKN veya TCKN
        :param company: Şirket kaydı
        :return: dict - Kullanıcı bilgileri
        """
        client, history = self._get_client(company)

        try:
            if hasattr(client.service, 'kayitliKullaniciListele'):
                result = client.service.kayitliKullaniciListele(
                    parametreler={
                        'urun': 'EFATURA',
                        'vknTckn': vkn_tckn
                    }
                )
            elif hasattr(client.service, 'kayitliKullaniciListeleExtended'):
                try:
                    result = client.service.kayitliKullaniciListeleExtended(
                        urun='EFATURA',
                        gecmisEklensin=1
                    )
                except Exception:
                    result = client.service.kayitliKullaniciListeleExtended(
                        parametreler={
                            'urun': 'EFATURA',
                            'gecmisEklensin': '1',
                        }
                    )
            else:
                return {'success': False, 'message': 'Kayıtlı kullanıcı sorgulama metodu bulunamadı'}

            if result:
                # Sonucu parse et
                users = []
                if not isinstance(result, list):
                    result = [result]
                for user in result:
                    user_dict = {
                        'vkn_tckn': user.get('vknTckn', ''),
                        'title': user.get('unvan', ''),
                        'alias': user.get('etiket', ''),
                        'first_creation_time': user.get('ilkOlusturmaZamani', ''),
                        'alias_creation_time': user.get('etiketOlusturmaZamani', ''),
                    }
                    if not vkn_tckn or user_dict.get('vkn_tckn') == vkn_tckn:
                        users.append(user_dict)
                return {'success': True, 'users': users}
            return {'success': False, 'message': 'Kayıtlı kullanıcı bulunamadı'}

        except Exception as e:
            _logger.error(f"Kayıtlı kullanıcı sorgulama hatası: {str(e)}")
            return {'success': False, 'message': str(e)}

    def get_registered_users_list(self, company=None):
        """
        Tüm kayıtlı e-Fatura kullanıcıları listesi
        :param company: Şirket kaydı
        :return: bytes - ZIP dosyası içeriği
        """
        client, history = self._get_client(company)

        try:
            try:
                result = client.service.kayitliKullaniciListeleExtended(
                    urun='EFATURA',
                    gecmisEklensin=1
                )
            except Exception:
                result = client.service.kayitliKullaniciListeleExtended(
                    parametreler={
                        'urun': 'EFATURA',
                        'gecmisEklensin': '1'
                    }
                )

            if result:
                return {'success': True, 'data': result}
            return {'success': False, 'message': 'Liste alınamadı'}

        except Exception as e:
            _logger.error(f"Kayıtlı kullanıcı listesi hatası: {str(e)}")
            return {'success': False, 'message': str(e)}

    # ============================================
    # E-FATURA GÖNDERİM İŞLEMLERİ
    # ============================================

    def send_invoice(self, invoice_xml, document_no, vkn, company=None, document_type='FATURA_UBL'):
        """
        e-Fatura gönder
        :param invoice_xml: Fatura XML içeriği
        :param document_no: Belge numarası
        :param vkn: Alıcı VKN
        :param company: Şirket kaydı
        :param document_type: Belge türü (FATURA_UBL, FATURA_CSXML)
        :return: dict - Gönderim sonucu
        """
        client, history = self._get_client(company)

        if isinstance(invoice_xml, str):
            invoice_xml = invoice_xml.encode('utf-8')

        doc_hash = self._generate_document_hash(invoice_xml)

        try:
            result = client.service.belgeGonderExt(
                parametreler={
                    'belgeNo': document_no,
                    'vergiTcKimlikNo': vkn,
                    'belgeTuru': document_type,
                    'veri': invoice_xml,
                    'belgeHash': doc_hash,
                    'mimeType': 'application/xml',
                    'belgeVersiyon': '1.2'
                }
            )

            if result:
                return {
                    'success': True,
                    'ettn': result.get('ettn', ''),
                    'belge_no': result.get('belgeNo', ''),
                    'message': 'Fatura başarıyla gönderildi'
                }
            return {'success': False, 'message': 'Gönderim sonucu alınamadı'}

        except Exception as e:
            _logger.error(f"Fatura gönderim hatası: {str(e)}")
            return {'success': False, 'message': str(e)}

    def send_invoice_with_response(self, invoice_xml, document_no, vkn, company=None):
        """
        e-Fatura gönder ve yanıt bekle (Ticari fatura senaryosu)
        """
        return self.send_invoice(invoice_xml, document_no, vkn, company)

    # ============================================
    # E-ARŞİV GÖNDERİM İŞLEMLERİ
    # ============================================

    def send_earchive_invoice(self, invoice_xml, document_no, company=None):
        """
        e-Arşiv fatura gönder
        :param invoice_xml: Fatura XML içeriği
        :param document_no: Belge numarası
        :param company: Şirket kaydı
        :return: dict - Gönderim sonucu
        """
        client, history = self._get_client(company)

        if isinstance(invoice_xml, str):
            invoice_xml = invoice_xml.encode('utf-8')

        doc_hash = self._generate_document_hash(invoice_xml)

        try:
            result = client.service.belgeGonderExt(
                parametreler={
                    'belgeNo': document_no,
                    'belgeTuru': 'EARSIV_FATURA',
                    'veri': invoice_xml,
                    'belgeHash': doc_hash,
                    'mimeType': 'application/xml',
                    'belgeVersiyon': '1.2'
                }
            )

            if result:
                return {
                    'success': True,
                    'ettn': result.get('ettn', ''),
                    'belge_no': result.get('belgeNo', ''),
                    'message': 'e-Arşiv fatura başarıyla gönderildi'
                }
            return {'success': False, 'message': 'Gönderim sonucu alınamadı'}

        except Exception as e:
            _logger.error(f"e-Arşiv fatura gönderim hatası: {str(e)}")
            return {'success': False, 'message': str(e)}

    # ============================================
    # E-İRSALİYE GÖNDERİM İŞLEMLERİ
    # ============================================

    def send_despatch(self, despatch_xml, document_no, vkn, company=None):
        """
        e-İrsaliye gönder
        :param despatch_xml: İrsaliye XML içeriği
        :param document_no: Belge numarası
        :param vkn: Alıcı VKN
        :param company: Şirket kaydı
        :return: dict - Gönderim sonucu
        """
        client, history = self._get_client(company)

        if isinstance(despatch_xml, str):
            despatch_xml = despatch_xml.encode('utf-8')

        doc_hash = self._generate_document_hash(despatch_xml)

        try:
            result = client.service.belgeGonderExt(
                parametreler={
                    'belgeNo': document_no,
                    'vergiTcKimlikNo': vkn,
                    'belgeTuru': 'IRSALIYE_UBL',
                    'veri': despatch_xml,
                    'belgeHash': doc_hash,
                    'mimeType': 'application/xml',
                    'belgeVersiyon': '1.2'
                }
            )

            if result:
                return {
                    'success': True,
                    'ettn': result.get('ettn', ''),
                    'belge_no': result.get('belgeNo', ''),
                    'message': 'e-İrsaliye başarıyla gönderildi'
                }
            return {'success': False, 'message': 'Gönderim sonucu alınamadı'}

        except Exception as e:
            _logger.error(f"e-İrsaliye gönderim hatası: {str(e)}")
            return {'success': False, 'message': str(e)}

    # ============================================
    # BELGE DURUM SORGULAMA
    # ============================================

    @staticmethod
    def _normalize_outgoing_belge_turu(document_type: str) -> str:
        """
        QNB gidenBelgeIndirExt için kabul edilen belge türleri sınırlı.
        Bazı yerlerden 'FATURA_UBL' gibi değerler gelebiliyor; burada normalize ediyoruz.
        Kabul edilenler: FATURA, IRSALIYE, UYGULAMA_YANITI
        """
        dt = (document_type or "").strip().upper()
        if dt in ("EFATURA", "EARSIV"):
            return "FATURA"
        if "FATURA" in dt:
            return "FATURA"
        if "IRSALIYE" in dt:
            return "IRSALIYE"
        if "UYGULAMA" in dt or "YANIT" in dt:
            return "UYGULAMA_YANITI"
        return dt or "FATURA"

    def get_document_status(self, ettn, document_type='EFATURA', company=None):
        """
        Belge durumu sorgula
        :param ettn: Evrensel Tekil Tanımlayıcı Numara
        :param document_type: Belge türü (EFATURA, EARSIV, EIRSALIYE)
        :param company: Şirket kaydı
        :return: dict - Belge durumu
        """
        client, history = self._get_client(company)

        try:
            if not company:
                company = self.env.company

            vkn = self._get_company_vkn(company)

            # WSDL versiyonları farklı olabiliyor:
            # - Bazılarında: gidenBelgeDurumSorgula(vergiTcKimlikNo, belgeOid)
            # - Bazılarında: gidenBelgeDurumSorgula(parametreler={urun, ettn})
            try:
                result = client.service.gidenBelgeDurumSorgula(
                    vergiTcKimlikNo=vkn,
                    belgeOid=ettn,
                )
            except TypeError:
                result = client.service.gidenBelgeDurumSorgula(
                    parametreler={
                        'urun': document_type,
                        'ettn': ettn
                    }
                )

            # Zeep obje veya dict olabilir
            if result and hasattr(result, "__dict__"):
                result = result.__dict__

            if result:
                return {
                    'success': True,
                    'status': result.get('durum', ''),
                    'status_code': result.get('durumKodu', ''),
                    'status_description': result.get('durumAciklamasi', ''),
                    'gib_status': result.get('gibDurum', ''),
                    'timestamp': result.get('zaman', '')
                }
            return {'success': False, 'message': 'Durum bilgisi alınamadı'}

        except Exception as e:
            msg = str(e)
            # Bazı durumlarda QNB tarafı “yerelden alınan belge bulunamadı” gibi bir mesaj döndürüyor.
            # Bu hata cron'larda çok sayıda belge için tekrarlanabildiğinden ERROR seviyesinde log şişirmesin.
            if "bulunamad" in msg.lower():
                _logger.warning(f"Belge durumu sorgulama uyarısı: {msg}")
            else:
                _logger.error(f"Belge durumu sorgulama hatası: {msg}")
            return {'success': False, 'message': str(e)}

    def get_document_history(self, ettn, document_type='EFATURA', company=None):
        """
        Belge tarihçesi sorgula
        """
        client, history = self._get_client(company)

        try:
            result = client.service.belgeTarihceSorgula(
                parametreler={
                    'urun': document_type,
                    'ettn': ettn
                }
            )

            if result:
                history_list = []
                for item in result:
                    history_list.append({
                        'status': item.get('durum', ''),
                        'timestamp': item.get('zaman', ''),
                        'description': item.get('aciklama', '')
                    })
                return {'success': True, 'history': history_list}
            return {'success': False, 'message': 'Tarihçe bilgisi alınamadı'}

        except Exception as e:
            _logger.error(f"Belge tarihçesi sorgulama hatası: {str(e)}")
            return {'success': False, 'message': str(e)}

    # ============================================
    # GELEN BELGE İŞLEMLERİ
    # ============================================

    def get_incoming_documents(self, start_date, end_date, document_type='EFATURA', company=None):
        """
        Gelen belgeleri listele
        :param start_date: Başlangıç tarihi
        :param end_date: Bitiş tarihi
        :param document_type: Belge türü
        :param company: Şirket kaydı
        :return: dict - Gelen belgeler listesi
        """
        client, history = self._get_client(company)

        try:
            # QNB API signature: vergiTcKimlikNo, sonAlinanBelgeSiraNumarasi, belgeTuru
            # VKN şirketten al
            if not company:
                company = self.env.company

            vkn = self._get_company_vkn(company)

            # QNB API belge türü: 'FATURA', 'IRSALIYE', 'UYGULAMA_YANITI', 'IRSALIYE_YANITI'
            # 'EFATURA' değil, 'FATURA' kullanılmalı
            belge_turu = 'FATURA' if document_type == 'EFATURA' else document_type

            # ===== SAYFALAMA İLE TÜM BELGELERİ ÇEK =====
            all_results = []
            last_sequence = '0'
            page = 1
            max_pages = 500  # Güvenlik limiti (büyük arşivlerde 50 sayfa yetmeyebilir)

            while page <= max_pages:
                result = client.service.gelenBelgeleriListele(
                    vergiTcKimlikNo=vkn,
                    sonAlinanBelgeSiraNumarasi=last_sequence,
                    belgeTuru=belge_turu
                )

                if not result:
                    break

                # Liste mi tek obje mi?
                if not isinstance(result, list):
                    result = [result]

                _logger.info(f"QNB: Sayfa {page}, sequence={last_sequence}, belgeler={len(result)}")

                # Sonuçları ekle
                all_results.extend(result)

                # Sequence numarasını güncelle (son belgenin sequence'ı)
                if len(result) > 0:
                    last_doc = result[-1]
                    if hasattr(last_doc, 'belgeSiraNo'):
                        new_sequence = str(last_doc.belgeSiraNo)
                        if new_sequence == last_sequence:
                            # Aynı sequence geldi, dur
                            break
                        last_sequence = new_sequence
                    else:
                        # belgeSiraNo yok, tek sayfa var
                        break

                # 100'den az geldi mi? (son sayfa)
                if len(result) < 100:
                    break

                page += 1

            # Tüm sonuçları işle
            if all_results:
                documents = []
                for doc in all_results:
                    # doc bir dict veya obje olabilir
                    if hasattr(doc, '__dict__'):
                        # Obje ise dict'e çevir
                        doc_dict = doc.__dict__ if hasattr(doc, '__dict__') else {}
                    elif isinstance(doc, dict):
                        doc_dict = doc
                    else:
                        # Zeep objesi ise
                        doc_dict = {}
                        for attr in dir(doc):
                            if not attr.startswith('_'):
                                try:
                                    doc_dict[attr] = getattr(doc, attr)
                                except:
                                    pass

                    documents.append({
                        'ettn': doc_dict.get('ettn', '') or getattr(doc, 'ettn', ''),
                        'belge_no': doc_dict.get('belgeNo', '') or getattr(doc, 'belgeNo', '') or doc_dict.get('belge_no', ''),
                        # QNB gelen listele alanları WSDL'e göre değişebiliyor (gonderenVknTckn / gonderenIsim)
                        'sender_vkn': (
                            doc_dict.get('gonderenVknTckn', '')
                            or doc_dict.get('gonderenVkn', '')
                            or getattr(doc, 'gonderenVknTckn', '')
                            or getattr(doc, 'gonderenVkn', '')
                        ),
                        'sender_title': (
                            doc_dict.get('gonderenIsim', '')
                            or doc_dict.get('gonderenUnvan', '')
                            or getattr(doc, 'gonderenIsim', '')
                            or getattr(doc, 'gonderenUnvan', '')
                        ),
                        'date': doc_dict.get('belgeTarihi', '') or getattr(doc, 'belgeTarihi', ''),
                        'total': float(doc_dict.get('toplamTutar', 0) or getattr(doc, 'toplamTutar', 0) or 0),
                        'currency': doc_dict.get('paraBirimi', 'TRY') or getattr(doc, 'paraBirimi', 'TRY'),
                        'status': doc_dict.get('durum', '') or getattr(doc, 'durum', '')
                    })
                # gelenBelgeleriListele API'si tarih aralığı parametresi almadığı için,
                # burada filtreleyerek çağıran tarafta aralık bazlı çekimi mümkün kılıyoruz.
                start_d = self._parse_qnb_date(start_date)
                end_d = self._parse_qnb_date(end_date)
                if start_d and end_d:
                    documents = [
                        d for d in documents
                        if (self._parse_qnb_date(d.get('date')) and start_d <= self._parse_qnb_date(d.get('date')) <= end_d)
                    ]

                return {'success': True, 'documents': documents}
            return {'success': True, 'documents': []}

        except Exception as e:
            _logger.error(f"Gelen belgeler listeleme hatası: {str(e)}")
            return {'success': False, 'message': str(e)}

    def download_incoming_document(self, ettn, document_type='EFATURA', company=None):
        """
        Gelen belgeyi indir
        :param ettn: ETTN
        :param document_type: Belge türü
        :param company: Şirket kaydı
        :return: dict - Belge içeriği
        """
        client, history = self._get_client(company)

        try:
            # QNB API signature: vergiTcKimlikNo, belgeEttn, belgeTuru, belgeFormati
            if not company:
                company = self.env.company

            vkn = self._get_company_vkn(company)

            belge_turu = 'FATURA' if document_type == 'EFATURA' else document_type

            result = client.service.gelenBelgeIndirExt(
                vergiTcKimlikNo=vkn,
                belgeEttn=ettn,
                belgeTuru=belge_turu,
                belgeFormati='UBL'  # QNB API: HTML, PDF veya UBL formatları
            )

            if result:
                return {
                    'success': True,
                    'content': result,
                    'format': 'XML'
                }
            return {'success': False, 'message': 'Belge indirilemedi'}

        except Exception as e:
            _logger.error(f"Belge indirme hatası: {str(e)}")
            return {'success': False, 'message': str(e)}

    def download_document_pdf(self, ettn, document_type='EFATURA', company=None):
        """
        Belge PDF'ini indir
        """
        client, history = self._get_client(company)

        try:
            result = client.service.gelenBelgeIndir(
                parametreler={
                    'urun': document_type,
                    'ettn': ettn,
                    'format': 'PDF'
                }
            )

            if result:
                return {
                    'success': True,
                    'content': result,
                    'format': 'PDF'
                }
            return {'success': False, 'message': 'PDF indirilemedi'}

        except Exception as e:
            _logger.error(f"PDF indirme hatası: {str(e)}")
            return {'success': False, 'message': str(e)}

    # ============================================
    # GİDEN BELGE İŞLEMLERİ
    # ============================================

    def get_outgoing_documents(self, start_date, end_date, document_type='EFATURA', company=None):
        """
        Giden belgeleri listele
        QNB API Signature: parametreler object içinde tüm parametreler
        """
        client, history = self._get_client(company)

        if not company:
            company = self.env.company

        # VKN'yi al
        vkn = self._get_company_vkn(company)

        # Belge türü: FATURA, IRSALIYE
        # QNB outbox için yaygın değerler: FATURA, FATURA_UBL, UYGULAMA_YANITI(_UBL), IRSALIYE(_UBL), ...
        # 'EFATURA' gibi Odoo içi kavramları normalize ediyoruz.
        belge_turu = 'FATURA' if document_type in ('EFATURA', 'EARSIV') else document_type

        try:
            result = client.service.gidenBelgeleriListele(
                parametreler={
                    'baslangicBelgeTarihi': start_date.strftime('%Y%m%d'),
                    'baslangicGonderimTarihi': start_date.strftime('%Y%m%d'),
                    'belgeTuru': belge_turu,
                    'bitisBelgeTarihi': end_date.strftime('%Y%m%d'),
                    'bitisGonderimTarihi': end_date.strftime('%Y%m%d'),
                    'vkn': vkn
                }
            )

            if result:
                documents = []
                # result bir liste veya tek bir obje olabilir
                if not isinstance(result, list):
                    result = [result]

                for doc in result:
                    # Zeep objesi olabilir
                    if hasattr(doc, '__dict__'):
                        doc_dict = doc.__dict__ if hasattr(doc, '__dict__') else {}
                    elif isinstance(doc, dict):
                        doc_dict = doc
                    else:
                        doc_dict = {}
                        for attr in dir(doc):
                            if not attr.startswith('_'):
                                try:
                                    doc_dict[attr] = getattr(doc, attr)
                                except:
                                    pass

                    documents.append({
                        'ettn': doc_dict.get('ettn', '') or getattr(doc, 'ettn', ''),
                        'belge_no': doc_dict.get('belgeNo', '') or getattr(doc, 'belgeNo', ''),
                        'recipient_vkn': doc_dict.get('aliciVkn', '') or getattr(doc, 'aliciVkn', ''),
                        'recipient_title': doc_dict.get('aliciUnvan', '') or getattr(doc, 'aliciUnvan', ''),
                        'receiver_vkn': doc_dict.get('aliciVkn', '') or getattr(doc, 'aliciVkn', ''),
                        'receiver_title': doc_dict.get('aliciUnvan', '') or getattr(doc, 'aliciUnvan', ''),
                        'date': doc_dict.get('belgeTarihi', '') or getattr(doc, 'belgeTarihi', ''),
                        'total': float(doc_dict.get('toplamTutar', 0) or getattr(doc, 'toplamTutar', 0) or 0),
                        'currency': doc_dict.get('paraBirimi', 'TRY') or getattr(doc, 'paraBirimi', 'TRY'),
                        'status': doc_dict.get('durum', '') or getattr(doc, 'durum', '')
                    })
                return {'success': True, 'documents': documents}
            return {'success': True, 'documents': []}

        except Exception as e:
            _logger.error(f"Giden belgeler listeleme hatası: {str(e)}")
            return {'success': False, 'message': str(e)}

    def download_outgoing_document(self, ettn, document_type='FATURA_UBL', company=None, format_type='UBL'):
        """
        Giden belgeyi indir (UBL/PDF/HTML)
        QNB API signature: vergiTcKimlikNo, belgeEttn, belgeTuru, belgeFormati
        """
        client, history = self._get_client(company)

        try:
            if not company:
                company = self.env.company

            vkn = self._get_company_vkn(company)
            belge_turu = self._normalize_outgoing_belge_turu(document_type)

            result = client.service.gidenBelgeIndirExt(
                vergiTcKimlikNo=vkn,
                belgeEttn=ettn,
                belgeTuru=belge_turu,
                belgeFormati=format_type
            )

            if result:
                return {'success': True, 'content': result, 'format': format_type}
            return {'success': False, 'message': 'Belge indirilemedi'}

        except Exception as e:
            _logger.error(f"Giden belge indirme hatası: {str(e)}")
            return {'success': False, 'message': str(e)}

    # ============================================
    # UYGULAMA YANITI İŞLEMLERİ
    # ============================================

    def send_application_response(self, ettn, response_type, reason=None, company=None):
        """
        Uygulama yanıtı gönder (Kabul/Red)
        :param ettn: ETTN
        :param response_type: Yanıt türü (KABUL, RED)
        :param reason: Red sebebi
        :param company: Şirket kaydı
        """
        client, history = self._get_client(company)

        try:
            params = {
                'ettn': ettn,
                'yanitTuru': response_type
            }
            if reason:
                params['sebep'] = reason

            result = client.service.uygulamaYanitiGonder(parametreler=params)

            if result:
                return {
                    'success': True,
                    'message': f'Fatura {response_type.lower()} edildi'
                }
            return {'success': False, 'message': 'Yanıt gönderilemedi'}

        except Exception as e:
            _logger.error(f"Uygulama yanıtı gönderim hatası: {str(e)}")
            return {'success': False, 'message': str(e)}

    def accept_invoice(self, ettn, company=None):
        """Fatura kabul et"""
        return self.send_application_response(ettn, 'KABUL', company=company)

    def reject_invoice(self, ettn, reason, company=None):
        """Fatura reddet"""
        return self.send_application_response(ettn, 'RED', reason, company)

    # ============================================
    # KONTÖR İŞLEMLERİ
    # ============================================

    def get_credit_status(self, company=None):
        """
        Kontör (kredi) durumu sorgula
        Not: Bu WSDL versiyonunda kontorDurumSorgula metodu bulunmamaktadır
        Kontör bilgisi QNB panelinden manuel olarak kontrol edilmelidir
        """
        # Kontör sorgulama metodu bu WSDL'de bulunmadığından boş yanıt döndür
        _logger.info("Kontör durumu sorgulama - WSDL versiyonu desteği yok")
        return {
            'success': False,
            'message': 'Kontör sorgulama metodu bu WSDL versiyonunda desteklenmiyor. '
                      'Lütfen QNB panelinden kontör bilgisini kontrol edin: '
                      'https://www.qnbefinans.com.tr',
            'note': 'Mevcut metodlar: belgeGonderExt, gidenBelgeDurumSorgula, '
                   'belgeTarihceSorgula, gelenBelgeleriListele, gelenBelgeIndir, '
                   'uygulamaYanitiGonder, kayitliKullaniciListele'
        }
