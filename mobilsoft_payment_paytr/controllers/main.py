# -*- coding: utf-8 -*-
# Part of Kitayazilim. See LICENSE file for full copyright and licensing details.

"""PayTR Payment Controllers

This module provides the HTTP controllers needed for the PayTR payment flow,
including endpoints for generating iframe tokens and handling payment
notifications from the PayTR payment gateway.
"""

import hmac
import hashlib
import logging
import pprint
import base64
import psycopg2

from werkzeug.exceptions import Forbidden

import json
from odoo import http, _
from odoo.exceptions import ValidationError
from odoo.http import request
from odoo.addons.website_sale.controllers.payment import PaymentPortal

_logger = logging.getLogger(__name__)


class PayTRController(http.Controller):
    """Controller for PayTR Payment Gateway Integration

    This controller provides endpoints for the PayTR payment flow, including
    generating iframe tokens and handling payment notifications.
    """
    _return_url = '/payment/paytr/return'  # Endpoint for payment return notifications
    _iframe_token = '/payment/paytr/get-iframe-token'  # Endpoint for generating iframe tokens

    @http.route(_iframe_token, type='json', auth='public')
    def get_iframe_token(self, **data):
        """Generate an iframe token for PayTR payment.

        This endpoint is called by the frontend to obtain a token for the PayTR
        iframe. If a token already exists for the transaction, it returns that
        token. Otherwise, it generates a new token by making a request to the
        PayTR API.

        Args:
            data: Request data containing the transaction reference

        Returns:
            dict: Response containing the PayTR iframe token

        Raises:
            ValidationError: If there's an error generating the token
        """
        """ Simulate the response of a payment request.

        :param dict data: The simulated notification data.
        :return: None
        """
        ref = data.get('reference')
        tx_sudo = request.env['payment.transaction'].sudo().search([('reference', '=', ref)])
        if tx_sudo.provider_reference:
            return {'token': tx_sudo.provider_reference}
        else:
            IP = request.httprequest.remote_addr
            payload = tx_sudo.provider_id._paytr_generate_vals(tx_sudo, IP)
            code, resp = request.env['paytr.api'].sudo().send(payload)
            if code != 200:
                # Log detailed error information
                _logger.warning("PayTR API Error: Status code %s, Response: %s", code, resp)
                # Provide a user-friendly error message with translation support
                error_message = _("Payment gateway communication error (Code: %s). Please try again later.", code)
                raise ValidationError(error_message)

            res = json.loads(resp)
            transaction_status = res.get('status')
            if transaction_status == "success":
                tx_sudo.provider_reference = res.get('token')
                return res
            elif transaction_status == "failed":
                # More descriptive error message with transaction details
                error_message = _(
                    "Payment failed: %s (Code: %s). Please verify your payment details and try again.",
                    res.get("reason", _('Unknown payment gateway error')), code
                )
                _logger.info("Payment failed for transaction %s: %s (Code: %s)",
                          tx_sudo.reference, res.get("reason", _('Unknown payment gateway error')), code)
                raise ValidationError(error_message)
            else:
                # Log unexpected status with transaction details
                _logger.warning(
                    "PayTR: Received unexpected payment status '%s' for transaction %s",
                    transaction_status, tx_sudo.reference
                )
                # Generic error message for unexpected status
                error_message = _(
                    "Payment status could not be determined. Please contact customer support with reference: %s",
                    tx_sudo.reference
                )
                raise ValidationError(error_message)

    @http.route(
        _return_url, type='http', auth='public', methods=['POST'], csrf=False, save_session=False
    )
    def paytr_return_from_checkout(self, **data):
        """Process the notification data sent by PayTR after payment.

        This endpoint receives notifications from PayTR about payment status
        changes. It verifies the signature of the notification and processes
        the payment transaction accordingly.

        Args:
            data: Notification data from PayTR

        Returns:
            str: Acknowledgment response to PayTR

        Raises:
            Forbidden: If the notification signature is invalid
        """
        """ Process the notification data sent by Buckaroo after redirection from checkout.

        The route is flagged with `save_session=False` to prevent Odoo from assigning a new session
        to the user if they are redirected to this route with a POST request. Indeed, as the session
        cookie is created without a `SameSite` attribute, some browsers that don't implement the
        recommended default `SameSite=Lax` behavior will not include the cookie in the redirection
        request from the payment provider to Odoo. As the redirection to the '/payment/status' page
        will satisfy any specification of the `SameSite` attribute, the session of the user will be
        retrieved and with it the transaction which will be immediately post-processed.

        :param dict raw_data: The un-formatted notification data
        """
        _logger.info("handling redirection from PayTR with data:\n%s", pprint.pformat(data))

        # Check the integrity of the notification
        received_signature = data.get('hash')
        tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data(
            'paytr', data
        )
        self._verify_notification_signature(data, received_signature, tx_sudo)

        # Handle the notification data
        tx_sudo._handle_notification_data('paytr', data)
        return "OK"

    @staticmethod
    def _verify_notification_signature(notification_data, received_signature, tx_sudo):
        """Verify the signature of a PayTR notification.

        This method checks that the signature received with the notification
        matches the expected signature calculated using the merchant key and salt.

        Args:
            notification_data: The notification data from PayTR
            received_signature: The signature received with the notification
            tx_sudo: The transaction referenced by the notification

        Raises:
            Forbidden: If the signature is missing or invalid
        """
        """ Check that the received signature matches the expected one.

        :param dict notification_data: The notification data
        :param str received_signature: The signature received with the notification data
        :param recordset tx_sudo: The sudoed transaction referenced by the notification data, as a
                                  `payment.transaction` record
        :return: None
        :raise: :class:`werkzeug.exceptions.Forbidden` if the signatures don't match
        """
        # Check for the received signature
        if not received_signature:
            _logger.warning("PayTR Security Error: Received notification with missing signature")
            # Use Forbidden exception to prevent potential security issues
            raise Forbidden(_('Payment notification rejected due to security validation failure'))

        hash_str = notification_data['merchant_oid'] + tx_sudo.provider_id.paytr_merchant_salt + notification_data['status'] + notification_data['total_amount']
        expected_signature = base64.b64encode(hmac.new(tx_sudo.provider_id.paytr_merchant_key.encode(), hash_str.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(received_signature.encode(), expected_signature):
            _logger.warning("PayTR Security Error: Received notification with invalid signature")
            # Log additional details for debugging (without exposing sensitive data)
            _logger.debug("Signature validation failed for transaction reference: %s",
                       notification_data.get('merchant_oid', 'Unknown'))
            # Use Forbidden exception to prevent potential security issues
            raise Forbidden(_('Payment notification rejected due to security validation failure'))


class PaymentPortalMondialRelay(PaymentPortal):
    """Extended Payment Portal for PayTR

    This class extends the standard payment portal to handle unique constraint
    violations that may occur during payment transaction creation with PayTR.
    """

    @http.route()
    def shop_payment_transaction(self, *args, **kwargs):
        """Handle payment transaction creation for shop orders.

        This method overrides the standard shop_payment_transaction method to
        handle the case where a duplicate transaction might be created. If a
        UniqueViolation error occurs and there's an existing PayTR transaction
        in draft state, it returns that transaction instead of creating a new one.

        Args:
            args: Positional arguments
            kwargs: Keyword arguments

        Returns:
            dict: Processing values for the payment transaction

        Raises:
            Exception: If the error is not related to a duplicate PayTR transaction
        """
        try:
            return super().shop_payment_transaction(*args, **kwargs)
        except psycopg2.errors.UniqueViolation as e:
            last_tx_id = request.session.get('__website_sale_last_tx_id')
            last_tx = request.env['payment.transaction'].browse(last_tx_id).sudo().exists()
            if last_tx and last_tx.provider_id.code == 'paytr' and last_tx.provider_reference and last_tx.state == 'draft':
                return last_tx._get_processing_values()
            else:
                raise e
