# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import pprint

from werkzeug.urls import url_encode, url_join

from odoo import _, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment_bml.const import CURRENCY_MAPPING
from odoo.addons.payment_bml.const import PAYMENT_STATUS_MAPPING
from odoo.addons.payment_bml.controllers.main import BMLController


_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _get_specific_rendering_values(self, processing_values):
        """ Override of `payment` to return BML-specific rendering values.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic and specific processing values of the
                                       transaction.
        :return: The dict of provider-specific rendering values.
        :rtype: dict
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'bml':
            return res

        # Faisapay requires amount to be sent without decimal places. We use 2 digit currency exponent 
        # & multiply the amount by 100 to remove the decimal place
        # Initiate the payment
        currency_exponent = 2
        converted_amount = int(self.amount * 100);  #remove the decimals from the amount
        version = BMLController._version
        
        _logger.info(
                    "Returning Payment Request Rendering values for(PROVIDER ID)%s:\n(values)%s",
                    self.provider_id, pprint.pformat(processing_values),
                )
        
       
        #convert currency to ISO 4217 numeric 3-digit code
        currency_code_numeric = CURRENCY_MAPPING[self.currency_id.name]
        
        base_url = self.provider_id.get_base_url()
        return_url_params = {'reference': self.reference}
        passcode = self.provider_id.bml_passcode
        

        rendering_values = {
            'api_url': self.provider_id._bml_get_api_url(),
            'Version': version,
            'MerID': self.provider_id.faisapay_merchant_id,
            'AcqID': self.provider_id.faisapay_acquirer_id,
            'OrderID': self.reference,
            'PurchaseAmt': converted_amount,
            'PurchaseCurrency': currency_code_numeric,
            'PurchaseCurrencyExponent': currency_exponent,
            'SignatureMethod': 'SHA1',
            'MerRespURL': url_join(
                base_url, f'{BMLController._return_url}?{url_encode(return_url_params)}'
            ),
        }
        
        rendering_values.update({
            'Signature': self.provider_id._bml_calculate_pay_request_signature(rendering_values)
        })
        
        return rendering_values


    def _send_capture_request(self):
        # Faisapay does not support capture request
        """ Override of `payment` to send a capture request to BML.

        Note: self.ensure_one()

        :return: None
        """
        super()._send_capture_request()
        if self.provider_code != 'bml':
            return

        raise UserError(_("Transactions processed by BML can't be captured manually"))


    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """ Override of `payment` to find the transaction based on bml data.

        :param str provider_code: The code of the provider that handled the transaction
        :param dict notification_data: The normalized notification data sent by the provider
        :return: The transaction if found
        :rtype: recordset of `payment.transaction`
        :raise: ValidationError if the data match no transaction
        """
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'bml' or len(tx) == 1:
            return tx

        _logger.info(
            "_get_tx_from_notification_data (notification_data)%s",
            notification_data
        )

        reference = notification_data.get('OrderID')
        if not reference:
            raise ValidationError("BML: " + _("Received data with missing reference."))

        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'bml')])

        if not tx:
            raise ValidationError(
                "BML: " + _("No transaction found matching reference %s.", reference)
            )

        return tx


    def _process_notification_data(self, notification_data):
        """ Override of `payment` to process the transaction based on BML data.

        Note: self.ensure_one()

        :param dict notification_data: The notification data sent by the provider
        :return: None
        """
        super()._process_notification_data(notification_data)
        if self.provider_code != 'bml':
            return

        _logger.info(
            "_process_notification_data (PROVIDER ID)%s:\n(notification_data)%s",
            self.provider_id, pprint.pformat(notification_data),
        )

        provider_reference = notification_data.get('ReferenceNo')
        response_code = notification_data.get('ResponseCode')
        reason_code = notification_data.get('ReasonCode')
        reason_text = notification_data.get('ReasonText')

        if provider_reference:
            self.provider_reference = provider_reference

        if not response_code:
            raise ValidationError("bml: " + _("Received data with missing response code."))

        if not reason_code:
            raise ValidationError("bml: " + _("Received data with missing reason code."))

        if response_code == '1' and reason_code in PAYMENT_STATUS_MAPPING['done']:
            self._set_done()
        elif response_code == '2' and reason_code in PAYMENT_STATUS_MAPPING['cancelled']:
            self._set_canceled()
        else:
            _logger.warning(
                "Received data with error code (%s) for transaction with primary"
                "(response code %s) and (reason code %s).", response_code, reason_code, self.reference
            )
            self._set_error("BML: " + _("An error occurred during the processing "
                                             "response code: %s,reason code %s, reason desc: %s ",
                                             response_code, reason_code, reason_text))
