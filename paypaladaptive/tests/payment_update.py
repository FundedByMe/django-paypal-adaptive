import json

from django.test import TestCase

from mock import patch

from .factories import PaymentFactory


class MockUpdateRequest(object):
    _response = None
    _code = None
    _base_response = {
        'responseEnvelope': {
            'ack': 'Success'
        }
    }

    @property
    def response(self):
        return self._response

    @property
    def code(self):
        return self._code

    def call(self, *args, **kwargs):
        return self

    @classmethod
    def set_response(cls, response):
        response.update(cls._base_response)
        cls._response = json.dumps(response)


class TestPaymentUpdate(TestCase):
    def setUp(self):
        self.payment = PaymentFactory.create(
            status='new', pay_key='AP-9HW83863H61516232')

    def test_parse_update_status(self):
        response = {'status': 'COMPLETED'}
        self.assertEqual(
            'completed', self.payment._parse_update_status(response))

        response = {'status': 'CREATED'}
        self.assertEqual(
            'created', self.payment._parse_update_status(response))

        response = {'status': 'ERROR'}
        self.assertEqual(
            'error', self.payment._parse_update_status(response))

        self.assertEqual('new', self.payment._parse_update_status({}))

    def test_get_update_kwargs(self):
        self.assertEqual({'payKey': self.payment.pay_key},
                         self.payment.get_update_kwargs())

        with self.assertRaises(ValueError) as context_manager:
            self.payment.pay_key = None
            self.payment.get_update_kwargs()

        self.assertEqual(context_manager.exception.message,
                         "Can't update unprocessed payments")

    @patch("paypaladaptive.api.endpoints.UrlRequest", MockUpdateRequest)
    def test_update(self):
        MockUpdateRequest.set_response({'status': 'COMPLETED'})

        self.payment.status = 'created'
        self.payment.update()
        self.assertEqual(self.payment.status, 'completed')

        MockUpdateRequest.set_response({'status': 'CREATED'})

        self.payment.update()
        self.assertEqual(self.payment.status, 'created')

        MockUpdateRequest.set_response({'status': 'ERROR'})

        self.payment.update()
        self.assertEqual(self.payment.status, 'error')

        self.payment.status = 'new'

        MockUpdateRequest.set_response({
            'status': 'an unrecognized weird value'})

        self.payment.update()
        self.assertEqual(self.payment.status, 'new')

