from oauthlib.oauth1 import RequestValidator
from ltilogin.models import LTIClient, KEY_LENGTH

class LTIRequestValidator(RequestValidator):
    
    @property
    def real_safe_characters(self):
        return super(LTIRequestValidator, self).safe_characters
    
    @property
    def safe_characters(self):
        """ Allow also '-' character used in some uuid examples out there. """
        return self.real_safe_characters.union(set('-'))

    @property
    def client_key_length(self):
        """ Loosen limits. """
        return KEY_LENGTH

    @property
    def nonce_length(self):
        """ Loosen limits. """
        return KEY_LENGTH

    @property
    def enforce_ssl(self):
        """ Allow unsafe access when using limited network. """
        return False

    def validate_timestamp_and_nonce(self, client_key, timestamp, nonce,
        request_token=None, access_token=None):
        """
        Should check if timestamp and nonce pair have been seen before.
        Here we trust the network and the client computer are completely secure.
        """
        return True

    def validate_client_key(self, client_key, request):
        return LTIClient.objects.filter(key=client_key).first() is not None

    def get_client_secret(self, client_key, request):
        return LTIClient.objects.filter(key=client_key).first().secret
