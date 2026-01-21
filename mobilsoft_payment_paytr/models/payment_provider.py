# -*- coding: utf-8 -*-
# Part of Kitayazilim. See LICENSE file for full copyright and licensing details.

"""Payment Provider Model Extensions for PayTR

This module extends the payment.provider model to add PayTR-specific
functionality and fields required for integration with the PayTR
payment gateway.
"""

import base64
import hmac
import hashlib
import json

from werkzeug import urls
from odoo import fields, models, api

class PaymentProvider(models.Model):
    """Payment Provider Model Extension for PayTR

    This class extends the payment.provider model to add PayTR-specific
    fields and methods required for the PayTR payment gateway integration.
    """
    _inherit = 'payment.provider'

    code = fields.Selection(selection_add=[('paytr', "PayTR")], ondelete={'paytr': 'set default'})
    paytr_merchant_id = fields.Char(string="Mağaza Numarası", required_if_provider='paytr')
    paytr_merchant_key = fields.Char(string="Mağaza Api Key", required_if_provider='paytr')
    paytr_merchant_salt = fields.Char(string="Mağaza Api Salt", required_if_provider='paytr')
    paytr_ok_url = fields.Char(string="Başarılı URL", default='/payment/status')
    paytr_fail_url = fields.Char(string="Hata URL", default='/payment/status')
    paytr_timeout = fields.Char(string="Aşımı süresi", default='30', help="İşlem zaman aşımı süresi")
    paytr_no_installment = fields.Boolean(string="Tek çekim", default=True, help="Taksit görüntülenmesin")
    paytr_max_installment = fields.Char(string="En fazla taksit sayısı", default='0', help="Gösterilecek en fazlataksit sayısını belirler! 1-12 taksit")

    @api.model
    def _get_compatible_providers(self, *args, currency_id=None, **kwargs):
        """Filter providers based on currency compatibility.

        PayTR only supports specific currencies (TRY, EUR, USD, GBP, RUB).
        This method filters out PayTR from the available providers when
        the selected currency is not supported.

        Args:
            currency_id: The ID of the currency to check compatibility with

        Returns:
            recordset: Compatible payment providers
        """
        """ Override of `payment` to unlist Bank of Georgia providers for unsupported currencies. """
        providers = super()._get_compatible_providers(*args, currency_id=currency_id, **kwargs)

        currency = self.env['res.currency'].browse(currency_id).exists()
        if currency and currency.name not in ['TL', 'TRY', 'EUR', 'USD', 'GBP', 'RUB']:
            providers = providers.filtered(lambda p: p.code != 'paytr')

        return providers

    def _paytr_generate_vals(self, tx, IP):
        """Generate the values for the PayTR API request.

        This method prepares all the necessary parameters required for
        initiating a payment request with the PayTR API, including merchant
        details, transaction information, and security tokens.

        Args:
            tx: The payment transaction record
            IP: The IP address of the customer

        Returns:
            dict: A dictionary containing all parameters for the PayTR API request
        """
        # API Entegrasyon Bilgileri - Mağaza paneline giriş yaparak BİLGİ sayfasından alabilirsiniz.
        merchant_id = self.paytr_merchant_id
        merchant_key = self.paytr_merchant_key
        merchant_salt = self.paytr_merchant_salt
        email = tx.partner_email or ''  # Müşterinizin sitenizde kayıtlı veya form vasıtasıyla aldığınız eposta adresi
        payment_amount = str(int(tx.amount * 100))  # Tahsil edilecek tutar.
        merchant_oid = tx.reference  # Sipariş numarası: Her işlemde benzersiz olmalıdır!! Bu bilgi bildirim sayfanıza yapılacak bildirimde geri gönderilir.
        user_name = tx.partner_name  # Müşterinizin sitenizde kayıtlı veya form aracılığıyla aldığınız ad ve soyad bilgisi
        user_address = tx.partner_address or 'TR'  # Müşterinizin sitenizde kayıtlı veya form aracılığıyla aldığınız adres bilgisi
        user_phone = tx.partner_phone or '1'  # Müşterinizin sitenizde kayıtlı veya form aracılığıyla aldığınız telefon bilgisi

        # Başarılı ödeme sonrası müşterinizin yönlendirileceği sayfa
        # !!! Bu sayfa siparişi onaylayacağınız sayfa değildir! Yalnızca müşterinizi bilgilendireceğiniz sayfadır!
        # !!! Siparişi onaylayacağız sayfa "Bildirim URL" sayfasıdır (Bakınız: 2.ADIM Klasörü).
        base_url = self.get_base_url()
        merchant_ok_url = urls.url_join(base_url, self.paytr_ok_url)

        # Ödeme sürecinde beklenmedik bir hata oluşması durumunda müşterinizin yönlendirileceği sayfa
        # !!! Bu sayfa siparişi iptal edeceğiniz sayfa değildir! Yalnızca müşterinizi bilgilendireceğiniz sayfadır!
        # !!! Siparişi iptal edeceğiniz sayfa "Bildirim URL" sayfasıdır (Bakınız: 2.ADIM Klasörü).
        merchant_fail_url = urls.url_join(base_url, self.paytr_fail_url)

        # Müşterinin sepet/sipariş içeriği
        # ÖRNEK $user_basket oluşturma - Ürün adedine göre array'leri çoğaltabilirsiniz
        basket_array = [
            [tx.reference, payment_amount, 1],
        ]
        user_basket = base64.b64encode(json.dumps(basket_array, ensure_ascii=False, separators=(',', ':')).encode()).decode()        # !!! Eğer bu örnek kodu sunucuda değil local makinanızda çalıştırıyorsanız
        # buraya dış ip adresinizi (https://www.whatismyip.com/) yazmalısınız. Aksi halde geçersiz paytr_token hatası alırsınız.
        user_ip = IP
        timeout_limit = self.paytr_timeout or '30'  # İşlem zaman aşımı süresi - dakika cinsinden
        debug_on = '1' if self.state == 'test' else '0'  # Hata mesajlarının ekrana basılması için entegrasyon ve test sürecinde 1 olarak bırakın. Daha sonra 0 yapabilirsiniz.
        test_mode = '1' if self.state == 'test' else '0'  # Mağaza canlı modda iken test işlem yapmak için 1 olarak gönderilebilir.
        no_installment = '0' if self.paytr_no_installment else '1'  # Taksit yapılmasını istemiyorsanız, sadece tek çekim sunacaksanız 1 yapın
        # Sayfada görüntülenecek taksit adedini sınırlamak istiyorsanız uygun şekilde değiştirin.
        # Sıfır (0) gönderilmesi durumunda yürürlükteki en fazla izin verilen taksit geçerli olur.
        max_installment = self.paytr_max_installment or '0'
        currency = tx.currency_id.name

        # Bu kısımda herhangi bir değişiklik yapmanıza gerek yoktur.
        # hash_str = merchant_id + user_ip + merchant_oid + email + payment_amount + user_basket.decode() + no_installment + max_installment + currency + test_mode
        hash_str = merchant_id + user_ip + merchant_oid + email + payment_amount + user_basket + no_installment + max_installment + currency + test_mode
        paytr_token = base64.b64encode(hmac.new(merchant_key.encode('utf-8'), (hash_str + merchant_salt).encode('utf-8'), hashlib.sha256).digest())
        payload = {
            'merchant_id': merchant_id,
            'merchant_oid': merchant_oid,
            'paytr_token': paytr_token.decode(),
            'payment_amount': payment_amount,
            'user_name': user_name,
            'user_address': user_address,
            'email': email,
            'user_phone': user_phone,
            'user_ip': user_ip,
            'user_basket': user_basket,
            'currency': currency,
            'no_installment': no_installment,
            'max_installment': max_installment,
            'lang': 'tr',
            'merchant_ok_url': merchant_ok_url,
            'merchant_fail_url': merchant_fail_url,
            'debug_on': debug_on,
            'test_mode': test_mode,
            'timeout_limit': timeout_limit,
        }
        return payload
