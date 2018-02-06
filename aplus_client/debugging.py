import json
import logging


TEST_URL_PREFIX = "http://testserver.testserver/api/v2/"
TEST_DATA_PATH = "test_api"

logger = logging.getLogger('aplus_client.client')


class FakeResponse:
    def __init__(self, url, status_code, text):
        self.url = url
        self.status_code = status_code
        self.text = text

    def json(self):
        try:
            return json.loads(self.text) if self.text else None
        except ValueError as e:
            raise RuntimeError("Json error in {}: {}".format(self.url, e))


class AplusClientDebugging:
    def do_get(self, url, **kwargs):
        if url.startswith(TEST_URL_PREFIX):
            furl = url[len(TEST_URL_PREFIX):].strip('/').replace('/', '__')
            fn = ''.join((TEST_DATA_PATH, '/', furl, ".json"))
            logger.debug("making test GET '%s', file=%r", url, fn)
            with open(fn, 'r') as f:
                return FakeResponse(fn, 200, f.read())
        return super().do_get(url, **kwargs)

    def do_post(self, url, data, **kwargs):
        if url.startswith(TEST_URL_PREFIX):
            logger.debug("making test POST '%s', data=%r", url, data)
            return FakeResponse(url, 200, "{'result': 'accepted'}")
        return super().do_post(url, data, **kwargs)


