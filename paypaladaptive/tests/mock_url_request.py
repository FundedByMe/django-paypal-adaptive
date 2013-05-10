import json

from django.core.urlresolvers import reverse
from django.contrib.sites.models import Site

from paypaladaptive import settings


class MockUrlRequest(object):
    def call(self, url, data=None, headers=None):
        self._assert_valid_url(url)
        self._assert_valid_data(json.loads(data))
        self._assert_valid_headers(headers)
        self._set_response()
        return self

    def _set_response(self):
        """Define JSON string returned by paypal"""
        raise NotImplementedError

    def _assert_valid_url(self, url):
        valid_url = "%s%s" % (settings.PAYPAL_ENDPOINT, self._endpoint_name())
        assert url == valid_url

    def _endpoint_name(self):
        """"Name of API call to paypal"""
        raise NotImplementedError

    def _assert_valid_return_url(self, url):
        raise NotImplementedError

    def _assert_valid_cancel_url(self, url):
        raise NotImplementedError

    def _assert_valid_data(self, data):
        self._assert_valid_return_url(data["returnUrl"])
        self._assert_valid_cancel_url(data["cancelUrl"])
        assert data["requestEnvelope"] == {"errorLanguage": "en_US"}

    def _assert_valid_headers(self, headers):
        self._assert_valid_header(headers, 'X-PAYPAL-SECURITY-SIGNATURE',
                                  settings.PAYPAL_SIGNATURE)
        self._assert_valid_header(headers, 'X-PAYPAL-REQUEST-DATA-FORMAT',
                                  'JSON')
        self._assert_valid_header(headers, 'X-PAYPAL-APPLICATION-ID',
                                  settings.PAYPAL_APPLICATION_ID)
        self._assert_valid_header(headers, 'X-PAYPAL-SECURITY-USERID',
                                  settings.PAYPAL_USERID)
        self._assert_valid_header(headers, 'X-PAYPAL-SECURITY-PASSWORD',
                                  settings.PAYPAL_PASSWORD)
        self._assert_valid_header(headers, 'X-PAYPAL-RESPONSE-DATA-FORMAT',
                                  'JSON')

    def _assert_valid_header(self, headers, name, value):
        assert headers[name] == value

    def _assert_valid_reversed_url(self, url, kwargs, template_name):
        """"Helper function for return and cancel urls"""
        current_site = Site.objects.get_current()
        return_url = reverse(template_name, kwargs=kwargs)
        assert url == "http://%s%s" % (current_site, return_url)

    @property
    def response(self):
        return self._response.data

    @property
    def code(self):
        return self._response.code