/** @odoo-module **/

import { _t } from '@web/core/l10n/translation';
import { loadJS } from '@web/core/assets';

import paymentForm from '@payment/js/payment_form';
import { RPCError } from '@web/core/network/rpc_service';

paymentForm.include({

    paytrData: undefined,

    // #=== DOM MANIPULATION ===#

    /**
     * Prepare the inline form of PayTR for direct payment.
     *
     * @private
     * @param {number} providerId - The id of the selected payment option's provider.
     * @param {string} providerCode - The code of the selected payment option's provider.
     * @param {number} paymentOptionId - The id of the selected payment option.
     * @param {string} paymentMethodCode - The code of the selected payment method, if any.
     * @param {string} flow - The online payment flow of the selected payment option.
     * @return {void}
     */
    async _prepareInlineForm(providerId, providerCode, paymentOptionId, paymentMethodCode, flow) {
        if (providerCode !== 'paytr') {
            this._super(...arguments);
            return;
        }

        // Check if the inline form values were already extracted.
        this.paytrData ??= {}; // Store the form data of each instantiated payment method.
        if (flow === 'token') {
            return; // Don't show the form for tokens.
        } else if (!document.getElementById('paytriframe')) {
            this._setPaymentFlow('direct'); // Overwrite the flow even if no re-instantiation.
            let html_src =  `<div id="paytr_modal" class="modal" tabindex="-1" role="dialog">` +
            '<div class="modal-dialog modal-lg" role="document">' +
                '<div class="modal-content">' +
                    '<div class="modal-body">'+
                        '<iframe  id="paytriframe" frameborder="0" scrolling="no" style="width: 100%;"></iframe>' +
                    '</div>' +
                '</div>' +
            '</div>' +
            '</div>';
            document.querySelector('main').insertAdjacentHTML('beforeend', html_src)
            return; // Don't re-extract the data if already done for this payment method.
        }

    },

    /**
     * Process the direct payment flow.
     *
     * @override method from payment.payment_form
     * @private
     * @param {string} providerCode - The code of the selected payment option's provider.
     * @param {number} paymentOptionId - The id of the selected payment option.
     * @param {string} paymentMethodCode - The code of the selected payment method, if any.
     * @param {object} processingValues - The processing values of the transaction.
     * @return {void}
     */
    async _processDirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode !== 'paytr') {
            this._super(...arguments);
            return;
        }

        // Initiate the payment
        this.rpc('/payment/paytr/get-iframe-token', {
            'reference': processingValues.reference,
            'providerId': processingValues.provider_id
        }).then( async (result) => {
            this._enableButton();
            // $('body').unblock();
            document.getElementById('paytriframe').src = `https://www.paytr.com/odeme/guvenli/${result.token}`;
            await loadJS("/payment_paytr_kt/static/src/lib/iframeResizer.min.js");
            window.iFrameResize({},'#paytriframe');
            $('#paytr_modal').modal('show');

        }).catch((error) => {
            if (error instanceof RPCError) {
                this._displayErrorDialog(_t("Payment processing failed"), error.data.message);
                this._enableButton();
            } else {
                return Promise.reject(error);
            }
        });
    },

});
