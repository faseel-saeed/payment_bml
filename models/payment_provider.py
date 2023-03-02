# Part of Odoo. See LICENSE file for full copyright and licensing details.

import hashlib
import hmac
import logging
import pprint
import base64

import requests
from werkzeug.urls import url_join

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.addons.payment_bml.const import SUPPORTED_CURRENCIES


_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('bml', "BML")], ondelete={'bml': 'set default'}
    )
    bml_merchant_id = fields.Char(
        string="BML Merchant Id",
        help="The key solely used to identify the merchant with BML.",
        required_if_provider='bml',
    )
    bml_acquirer_id = fields.Char(
        string="BML Acquirer",
        help="Acquirer id provided by BML",
        required_if_provider='bml',
        groups='base.group_system',
    )
    bml_passcode = fields.Char(
        string="Merchant Secret",
        required_if_provider='bml',

    )
    bml_live_url = fields.Char(
        string="Live URL",
        required_if_provider='bml',

    )
    bml_test_url = fields.Char(
        string="Test URL",
        required_if_provider='bml',

    )

    

    #=== COMPUTE METHODS ===#

    def _compute_feature_support_fields(self):
        """ Override of `payment` to enable additional features. """
        super()._compute_feature_support_fields()
        self.filtered(lambda p: p.code == 'bml').update({
            'support_manual_capture': False
        })

    # === BUSINESS METHODS ===#

    @api.model
    def _get_compatible_providers(self, *args, currency_id=None, **kwargs):
        """ Override of `payment` to filter out BML providers for unsupported currencies. """
        providers = super()._get_compatible_providers(*args, currency_id=currency_id, **kwargs)

        currency = self.env['res.currency'].browse(currency_id).exists()
        
        _logger.info(
            "Get compatible currency: BML: currency %s",
            currency.name
        )
        if currency and currency.name not in SUPPORTED_CURRENCIES:
            providers = providers.filtered(lambda p: p.code != 'bml')

        return providers
    
    def _bml_get_api_url(self):
        """ Return the URL of the API corresponding to the provider's state.

        :return: The API URL.
        :rtype: str
        """
        self.ensure_one()
        _logger.info(
            "GETTING API URL FOR STATE: %s",
            self.state
        )

        if self.state == 'enabled':
            return self.bml_live_url
        else:  # 'test'
            return self.bml_test_url


    
    def _bml_calculate_pay_request_signature(self, data):
        """ Compute the signature for the request according to the BML documentation.


        :param dict|bytes data: The data to sign.
        :return: The calculated signature.
        :rtype: str
        """ 

        merchant = self.bml_merchant_id
        acquirer = self.bml_acquirer_id
        secret = self.bml_passcode
            
        signing_string = f'{secret}{merchant}{acquirer}{data["orderID"]}{data["purchaseAmt"]}{data["purchaseCurrency"]}'
        return base64.b64encode(hashlib.sha1(signing_string.encode('utf-8')).digest()).decode('ASCII')
    

    
    def _bml_calculate_signature(self, data, is_redirect=True):
        """ Compute the signature for the request's data according to the BML documentation.


        :param dict|bytes data: The data to sign.
        :param bool is_redirect: Whether the data should be treated as redirect data
        :return: The calculated signature.
        :rtype: str
        """
        if is_redirect:
            merchant = self.bml_merchant_id
            acquirer = self.bml_acquirer_id
            secret = self.bml_passcode

            signing_string = f'{secret}{merchant}{acquirer}{data["orderID"]}'
            return base64.b64encode(hashlib.sha256(signing_string.encode('utf-8')).digest()).decode('ASCII')
        
        else:  # Notification data.
            merchant = self.bml_merchant_id
            acquirer = self.bml_acquirer_id
            secret = self.bml_passcode
            request_type = '0'; # request type 0 is payment
            
            signing_string = f'{secret}{merchant}{acquirer}{data["orderID"]}'
            return base64.b64encode(hashlib.sha1(signing_string.encode('utf-8')).digest()).decode('ASCII')
