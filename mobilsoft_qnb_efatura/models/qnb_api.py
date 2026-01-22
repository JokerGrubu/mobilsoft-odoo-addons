# -*- coding: utf-8 -*-
"""
QNB e-Solutions API Client
SOAP tabanlı web servisi ile iletişim
"""

import base64
import hashlib
import logging
import uuid
from datetime import datetime, timedelta
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
            result = client.service.kayitliKullaniciListele(
                parametreler={
                    'urun': 'EFATURA',
                    'vknTckn': vkn_tckn
                }
            )

            if result:
                # Sonucu parse et
                users = []
                for user in result:
                    users.append({
                        'vkn_tckn': user.get('vknTckn', ''),
                        'title': user.get('unvan', ''),
                        'alias': user.get('etiket', ''),
                        'first_creation_time': user.get('ilkOlusturmaZamani', ''),
                        'alias_creation_time': user.get('etiketOlusturmaZamani', ''),
                    })
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
            result = client.service.gidenBelgeDurumSorgula(
                parametreler={
                    'urun': document_type,
                    'ettn': ettn
                }
            )

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
            _logger.error(f"Belge durumu sorgulama hatası: {str(e)}")
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
            
            vkn = company.vat or company.qnb_username or ''
            if vkn:
                # Sadece rakamları al
                vkn = ''.join(filter(str.isdigit, str(vkn)))
            
            result = client.service.gelenBelgeleriListele(
                vergiTcKimlikNo=vkn,
                sonAlinanBelgeSiraNumarasi='0',  # 0 = tüm belgeler
                belgeTuru=document_type
            )

            if result:
                documents = []
                for doc in result:
                    documents.append({
                        'ettn': doc.get('ettn', ''),
                        'belge_no': doc.get('belgeNo', ''),
                        'sender_vkn': doc.get('gonderenVkn', ''),
                        'sender_title': doc.get('gonderenUnvan', ''),
                        'date': doc.get('belgeTarihi', ''),
                        'total': doc.get('toplamTutar', 0),
                        'currency': doc.get('paraBirimi', 'TRY'),
                        'status': doc.get('durum', '')
                    })
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
            result = client.service.gelenBelgeIndir(
                parametreler={
                    'urun': document_type,
                    'ettn': ettn,
                    'format': 'XML'
                }
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
        """
        client, history = self._get_client(company)

        try:
            result = client.service.gidenBelgeleriListele(
                parametreler={
                    'urun': document_type,
                    'baslangicTarihi': start_date.strftime('%Y-%m-%d'),
                    'bitisTarihi': end_date.strftime('%Y-%m-%d')
                }
            )

            if result:
                documents = []
                for doc in result:
                    documents.append({
                        'ettn': doc.get('ettn', ''),
                        'belge_no': doc.get('belgeNo', ''),
                        'receiver_vkn': doc.get('aliciVkn', ''),
                        'receiver_title': doc.get('aliciUnvan', ''),
                        'date': doc.get('belgeTarihi', ''),
                        'total': doc.get('toplamTutar', 0),
                        'currency': doc.get('paraBirimi', 'TRY'),
                        'status': doc.get('durum', '')
                    })
                return {'success': True, 'documents': documents}
            return {'success': True, 'documents': []}

        except Exception as e:
            _logger.error(f"Giden belgeler listeleme hatası: {str(e)}")
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
        """
        client, history = self._get_client(company)

        try:
            result = client.service.kontorDurumSorgula()

            if result:
                return {
                    'success': True,
                    'efatura_credit': result.get('efaturaKontor', 0),
                    'earchive_credit': result.get('earsivKontor', 0),
                    'edespatch_credit': result.get('eirsaliyeKontor', 0)
                }
            return {'success': False, 'message': 'Kontör durumu alınamadı'}

        except Exception as e:
            _logger.error(f"Kontör durumu sorgulama hatası: {str(e)}")
            return {'success': False, 'message': str(e)}
