import django.test as test

from mock import patch

from ..api.httpwrapper import UrlRequest, UrlResponse

class MockIPNVerifyRequest(UrlRequest):
    def call(self, url, data=None, headers=None):
        MockIPNVerifyRequest.data = data
        self._response = UrlResponse(data='VERIFIED', meta={}, code=200)
        return self


class MockIPNVerifyRequestInvalid(UrlRequest):
    data = None
    def call(self, url, data=None, headers=None):
        self.data = data
        self._response = UrlResponse(data='invalid', meta={}, code=200)
        return self


class MockIPNVerifyRequestFail(UrlRequest):
    data = None
    def call(self, url, data=None, headers=None):
        self.data = data
        self._response = UrlResponse(data='invalid', meta={}, code=None)
        return self


class MockIPNVerifyRequestInvalidCode(UrlRequest):
    data = None
    def call(self, url, data=None, headers=None):
        self.data = data
        self._response = UrlResponse(data='VERIFIED', meta={}, code=500)
        return self

@patch('paypaladaptive.api.ipn.endpoints.UrlRequest', MockIPNVerifyRequest)
def mock_ipn_call(data, url):
    c = test.Client()
    return c.post(url, data=data)