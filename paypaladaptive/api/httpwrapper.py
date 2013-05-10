import urllib2


class UrlResponse:
    def __init__(self, data, meta, code):
        self.data = data
        self.meta = meta
        self.code = code


class UrlRequest:
    def call(self, url, data=None, headers=None):
        if headers is None:
            headers = {}

        request = urllib2.Request(url, data=data, headers=headers)

        try:
            response = urllib2.urlopen(request)

            self._response = UrlResponse(response.read(), response.info(),
                                         response.getcode())
        except urllib2.URLError, e:
            self._response = UrlResponse(e.reason, {}, None)

        return self

    @property
    def response(self):
        return self._response.data

    @property
    def code(self):
        return self._response.code
