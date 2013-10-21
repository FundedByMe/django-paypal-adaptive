import json

from django.test import TestCase

from mock import patch

from .factories import PreapprovalFactory


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


class TestPreapprovalUpdate(TestCase):
    def setUp(self):
        self.preapproval = PreapprovalFactory.create(
            status='new', preapproval_key='PA-9HW83863H61516232')

    def test_parse_status(self):
        response = {'curPayments': 1,
                    'maxNumberOfPayments': 1}
        self.assertEqual(
            'used', self.preapproval._parse_update_status(response))
        
        response = {'status': 'ACTIVE', 'approved': 'true'}
        self.assertEqual(
            'approved', self.preapproval._parse_update_status(response))

        response = {'status': 'ACTIVE', 'approved': 'false'}
        self.assertEqual(
            'created', self.preapproval._parse_update_status(response))

        response = {'status': 'CANCELED'}
        self.assertEqual(
            'canceled', self.preapproval._parse_update_status(response))

        self.assertEqual('new', self.preapproval._parse_update_status({}))

    def test_get_update_kwargs(self):
        self.assertEqual({'preapprovalKey': self.preapproval.preapproval_key},
                         self.preapproval.get_update_kwargs())

        with self.assertRaises(ValueError) as context_manager:
            self.preapproval.preapproval_key = None
            self.preapproval.get_update_kwargs()

        self.assertEqual(context_manager.exception.message,
                         "Can't update unprocessed preapprovals")

    @patch("paypaladaptive.api.endpoints.UrlRequest", MockUpdateRequest)
    def test_update(self):
        MockUpdateRequest.set_response({
            'curPayments': 1,
            'maxNumberOfPayments': 1,
            'status': 'ACTIVE',
            'approved': 'true'
        })

        self.preapproval.status = 'created'
        self.preapproval.update()
        self.assertEqual(self.preapproval.status, 'used')

        MockUpdateRequest.set_response({
            'curPayments': 0,
            'maxNumberOfPayments': 1,
            'status': 'ACTIVE',
            'approved': 'true'
        })

        self.preapproval.update()
        self.assertEqual(self.preapproval.status, 'approved')

        MockUpdateRequest.set_response({
            'curPayments': 0,
            'maxNumberOfPayments': 1,
            'status': 'ACTIVE',
            'approved': 'false'
        })

        self.preapproval.update()
        self.assertEqual(self.preapproval.status, 'created')

        MockUpdateRequest.set_response({
            'curPayments': 0,
            'maxNumberOfPayments': 1,
            'status': 'CANCELED',
            'approved': 'true'
        })

        self.preapproval.update()
        self.assertEqual(self.preapproval.status, 'canceled')

