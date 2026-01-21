# -*- coding: utf-8 -*-
# Part of Kitayazilim. See LICENSE file for full copyright and licensing details.

import ctypes
import os
import logging

from odoo import models

_logger = logging.getLogger(__name__)

class PaymentRequest(ctypes.Structure):
    _fields_ = [
        ('merchant_id', ctypes.c_char_p),
        ('merchant_oid', ctypes.c_char_p),
        ('paytr_token', ctypes.c_char_p),
        ('payment_amount', ctypes.c_char_p),
        ('user_name', ctypes.c_char_p),
        ('user_address', ctypes.c_char_p),
        ('email', ctypes.c_char_p),
        ('user_phone', ctypes.c_char_p),
        ('user_ip', ctypes.c_char_p),
        ('user_basket', ctypes.c_char_p),
        ('currency', ctypes.c_char_p),
        ('no_installment', ctypes.c_char_p),
        ('max_installment', ctypes.c_char_p),
        ('lang', ctypes.c_char_p),
        ('merchant_ok_url', ctypes.c_char_p),
        ('merchant_fail_url', ctypes.c_char_p),
        ('debug_on', ctypes.c_char_p),
        ('test_mode', ctypes.c_char_p),
        ('timeout_limit', ctypes.c_char_p),
    ]


_lib = None
def _load_c_lib():
    global _lib
    if _lib:
        return _lib

    lib_name = "paytr"
    lib_path = None

    possible_paths = [
        os.path.join(os.path.dirname(__file__), f"lib{lib_name}.so"),
        os.path.join(os.path.dirname(__file__), "..", "lib64", f"lib{lib_name}.so"),
        os.path.join(os.path.dirname(__file__), "..", "lib", f"lib{lib_name}.so"),
    ]

    for path in possible_paths:
        if os.path.exists(path):
            lib_path = path
            break

    if not lib_path:
        raise ImportError(f"Cannot find the {lib_name} library")

    try:
        _lib = ctypes.CDLL(lib_path)

        _lib.myfree.argtypes = [ctypes.c_void_p]

        _lib.call_api.argtypes = [
            ctypes.POINTER(PaymentRequest),
            ctypes.c_char_p,
            ctypes.c_size_t
        ]
        _lib.call_api.restype = ctypes.c_int

    except Exception as e:
        raise ImportError(f"Error loading the library: {str(e)}")

    return _lib


class PaytrAPI(models.AbstractModel):
    _name = 'paytr.api'
    _description = 'Paytr API Interface'

    @property
    def lib(self):
        return _load_c_lib()

    def send(self, data):
        request = PaymentRequest(
            data.get('merchant_id', '').encode('utf-8'),
            data.get('merchant_oid', '').encode('utf-8'),
            data.get('paytr_token', '').encode('utf-8'),
            data.get('payment_amount', '').encode('utf-8'),
            data.get('user_name', '').encode('utf-8'),
            data.get('user_address', '').encode('utf-8'),
            data.get('email', '').encode('utf-8'),
            data.get('user_phone', '').encode('utf-8'),
            data.get('user_ip', '').encode('utf-8'),
            data.get('user_basket', '').encode('utf-8'),
            data.get('currency', '').encode('utf-8'),
            data.get('no_installment', '').encode('utf-8'),
            data.get('max_installment', '').encode('utf-8'),
            data.get('lang', '').encode('utf-8'),
            data.get('merchant_ok_url', '').encode('utf-8'),
            data.get('merchant_fail_url', '').encode('utf-8'),
            data.get('debug_on', '').encode('utf-8'),
            data.get('test_mode', '').encode('utf-8'),
            data.get('timeout_limit', '').encode('utf-8')
        )

        response_buffer = ctypes.create_string_buffer(4096)
        result = self.lib.call_api(
            ctypes.byref(request),  # PaymentRequest yapısı
            response_buffer,  # Yanıt tamponu
            ctypes.sizeof(response_buffer)  # Tampon boyutu
        )

        return result, response_buffer.value.decode('utf-8')
