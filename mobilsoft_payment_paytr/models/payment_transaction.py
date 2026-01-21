# -*- coding: utf-8 -*-
# Part of Kitayazilim. See LICENSE file for full copyright and licensing details.

"""Payment Transaction Model Extensions for PayTR

This module extends the payment.transaction model to add PayTR-specific
functionality for handling payment transactions through the PayTR
payment gateway.
"""

import logging
import re
from odoo import _, api, models
from odoo.exceptions import ValidationError


_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    """Payment Transaction Model Extension for PayTR

    This class extends the payment.transaction model to add PayTR-specific
    methods for handling transaction references and processing payment
    notifications from the PayTR payment gateway.
    """
    _inherit = 'payment.transaction'

    @api.model
    def _compute_reference(self, provider_code, prefix=None, separator='-', **kwargs):
        """Compute a unique reference for the transaction.

        For PayTR, we need to ensure that the reference contains only alphanumeric
        characters without any special characters or spaces, as required by the
        PayTR API specifications.

        Args:
            provider_code: The code of the payment provider
            prefix: Optional prefix for the reference
            separator: The separator to use between prefix and reference

        Returns:
            str: A unique transaction reference
        """
        if provider_code != 'paytr':
            return super()._compute_reference(provider_code, prefix=prefix, **kwargs)

        return super()._compute_reference(provider_code, prefix=re.sub(r'[\W]', '', prefix or ''), separator="", **kwargs)

    @api.model
    def _compute_reference_prefix(self, provider_code, separator, **values):
        """Compute the reference prefix from the transaction values.

        For PayTR, we need to ensure that the reference prefix contains only
        alphanumeric characters without any special characters or spaces.

        Args:
            provider_code: The code of the payment provider
            separator: The separator to use between prefix and reference
            values: The transaction values used to compute the reference prefix

        Returns:
            str: The computed reference prefix
        """
        """ Compute the reference prefix from the transaction values.

        Note: This method should be called in sudo mode to give access to the documents (invoices,
        sales orders) referenced in the transaction values.

        :param str provider_code: The code of the provider handling the transaction.
        :param str separator: The custom separator used to separate parts of the computed
                              reference prefix.
        :param dict values: The transaction values used to compute the reference prefix.
        :return: The computed reference prefix.
        :rtype: str
        """
        if provider_code != 'paytr':
            return super()._compute_reference_prefix(provider_code, separator, **values)

        prefix = super()._compute_reference_prefix(provider_code, separator="", **values)

        return re.sub(r'[\W]', '', prefix or '')

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """Find the transaction based on PayTR notification data.

        This method retrieves the transaction record corresponding to the
        notification data received from PayTR after a payment attempt.

        Args:
            provider_code: The code of the payment provider
            notification_data: The normalized notification data from PayTR

        Returns:
            recordset: The transaction if found

        Raises:
            ValidationError: If no transaction is found matching the reference
        """
        """ Override of payment to find the transaction based on Buckaroo data.

        :param str provider_code: The code of the provider that handled the transaction
        :param dict notification_data: The normalized notification data sent by the provider
        :return: The transaction if found
        :rtype: recordset of `payment.transaction`
        :raise: ValidationError if the data match no transaction
        """
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'paytr':
            return tx

        reference = notification_data.get('merchant_oid')
        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'paytr')])
        if not tx:
            raise ValidationError(
                "PayTR: " + _("No transaction found matching reference %s.", reference)
            )

        return tx

    def _process_notification_data(self, notification_data):
        """Process the transaction based on PayTR notification data.

        This method updates the transaction status based on the notification
        data received from PayTR. It handles success and failure cases.

        Args:
            notification_data: The normalized notification data from PayTR

        Raises:
            ValidationError: If inconsistent data were received
        """
        """ Override of payment to process the transaction based on Buckaroo data.

        Note: self.ensure_one()

        :param dict notification_data: The normalized notification data sent by the provider
        :return: None
        :raise: ValidationError if inconsistent data were received
        """
        super()._process_notification_data(notification_data)
        if self.provider_code != 'paytr':
            return

        transaction_status = notification_data.get('status')
        if not transaction_status:
            raise ValidationError("PayTR: " + _("Received data with missing transaction status"))

        code = notification_data.get('failed_reason_code', '')
        msg = notification_data.get('failed_reason_msg', '')

        if transaction_status == "success":
            self._set_done()
        elif transaction_status == "failed":
            self._set_error(_(
                "An error occurred during processing of your payment. Please try again."
                "(%s) %s",
                code, msg
            ))
        else:
            _logger.warning(
                "received data with invalid payment status (%s) for transaction with reference %s",
                transaction_status, self.reference
            )
            self._set_error("PayTR: " + _("Unknown status! Message: %s", msg))
