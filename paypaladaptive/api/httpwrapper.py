import urllib2

class UrlRequest(object):
    def run(self, url, data=None, headers=None):
        if headers is None:
            headers = {}

        request = urllib2.Request(url, data=data, headers=headers)

        try:
            return urllib2.urlopen(request).read()
        except urllib2.URLError, e:
            return e.read()