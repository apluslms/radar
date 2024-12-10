DEBUG = True
#SECRET_KEY = 'not a very secret key'
ADMINS = (
)
# NOTE: All other services define this in settings.py
ALLOWED_HOSTS = ["*"]

STATIC_ROOT = '/local/radar/static/'
MEDIA_ROOT = '/local/radar/media/'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'radar',
    },
}

PROVIDERS['a+'].update({'host': 'http://localhost:8000'})

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': '/run/radar/django-cache',
    },
    "exercise_templates": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": "/run/radar/django_cache_exercises",
        "TIMEOUT": 3600,
        "OPTIONS": {
            "MAX_ENTRIES": 100,
        },
    },
}

#CELERY_BROKER_URL = "amqp://"
CELERY_RESULT_BACKEND = 'file:///var/celery/results'

LOGGING['loggers'].update({
    '': {
        'level': 'INFO',
        'handlers': ['debug_console'],
        'propagate': True,
    },
    #'django.db.backends': {
    #    'level': 'DEBUG',
    #},
})

APLUS_AUTH_LOCAL = {
    "UID": "radar",
    "PRIVATE_KEY": """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEAvddPdRsfeYjTK/aVnX/J52exmXiu7ZXLx2W83brLmxaOGR1Z
b0qFt+0rtvBAx+s9KjlRj8rmMBLpTUTWWeaiMpVHkhMH+MHAcL8jCfM8G5nLqcg2
j50VBfXEiKT0QtonkOH+HVLYrtR0ZRQt4i9/8XLi1z+oITlH30yqs19PvZVksIJj
ReLqRDI1bxdzs6296i2Js5PyvGNKY1cn52dqMgMysg9P3HeuwAQW2jXQwxPn4HhN
oKlQL2SpNvInWwmpS1PrXgIhEvEq+T79GcxIeGJ1Rjhi6HY9jhFMYBh23EirAa+H
RBAbcyQ01Cc8hUa2YoNoolD/3oadsfQshps88wIDAQABAoIBADw75rAnbPMo4Kfg
U1RnyW4szoL9cbNchg28UBKiRBvvKiL51vii0o6rJ+WhkUxdbUjKawCOxj6WoYOs
xb48mVYnW1ATzcG16BNd8gYkMPwo7h/usLEcjCEZ+8PHYuEbStaDfhdbw/ik3FF9
95j+rT+0zhixz+zKue017CuBoFFsWypzMhT9encn/+9xGmAg8XTnxRSoVEdAQRqb
CkkmE/Y97HbbOALMijiK9h/bcIpY66X3EcmYTXXfNz/Bct9nh/wByoZErMsePWTF
vKMd2DJO72fWhSoxUjawZkuBSnKtmNNjomTf+TI/5ElC1OxfKaOOO2Z2UD3XuaFJ
nrGk9rECgYEA6TTVPuWuokEZI1k+R02zz/5HXDgvRmk7Rnm/OtiNcvAfTNXmEE8E
rB7jhBFKaVqFPUZk5+nySy9yPn+8IbKd6pGvU3zBNIBnFG7eHLwSET6ZXxeJAwXI
V0gmxEMBlnuHamv0tIfxhmNMSm+CmKjhh9ihg9ihKwgO1PzJ6MpeCzUCgYEA0GVp
xLcT6NBSFTgiehEvUOfe3W3VYiR3LBX2HuRAAyu07yIRehR44erbZo2CxzFJVFzt
5nstOBbctezncaqO3Tz1Gi5uKsvGItCQLvmn2xYkkA3dO+Ds1F9X927doTi+J+z2
KoH7Mun17H8ZOayHL3DXyWYqkNpobRMu2DfMhIcCgYBHQb565oFy0INW2rj93o83
2ZGCayR+1j6nbSHyYCLwYNCfkKgoiYx670FDpGjhQih+LZk9h61iLdAxqqQYg9Re
zT8OOotqeGWGx82UaB75J/CDLtTNmKG7ka9Ovs6oZXxeFziBRRyWnJa+E86KyOeI
s7e+ap3sYRzvFYK4X8VWlQKBgQChbU1HEkIb3/MVeMxMHi+2zkY25DOcuH6P6dsj
BtAHJL4dVxiOpnkVF2YoxIl/X1BcRzgJh3T5s8v4KLEHvYS5H9UFGN5BzGOI6GIn
4UADV92usO6kyZDq2Yg8pOaNUnUKXGY7e0Boqg7TyYhywpBdUV32JmvmlSi7BVcO
KfsE1QKBgAV6lcvROuw4Hk3tIErl4PeuOHXXfcOUkL/XaCd5QA5kd3QmhVOSIUB5
5LAofJqVerWgbRdgftf9wt4aLkt+fCVmtGoDgRJvNS9+yhv//XlnQGMnqJ4U99U5
OOw0h/x9BLfBbvSd0szfDhz7QZB55VHVo8zoIXNYQ5wsdIu2GlcS
-----END RSA PRIVATE KEY-----""",
    "PUBLIC_KEY": """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAvddPdRsfeYjTK/aVnX/J
52exmXiu7ZXLx2W83brLmxaOGR1Zb0qFt+0rtvBAx+s9KjlRj8rmMBLpTUTWWeai
MpVHkhMH+MHAcL8jCfM8G5nLqcg2j50VBfXEiKT0QtonkOH+HVLYrtR0ZRQt4i9/
8XLi1z+oITlH30yqs19PvZVksIJjReLqRDI1bxdzs6296i2Js5PyvGNKY1cn52dq
MgMysg9P3HeuwAQW2jXQwxPn4HhNoKlQL2SpNvInWwmpS1PrXgIhEvEq+T79GcxI
eGJ1Rjhi6HY9jhFMYBh23EirAa+HRBAbcyQ01Cc8hUa2YoNoolD/3oadsfQshps8
8wIDAQAB
-----END PUBLIC KEY-----""",
    "REMOTE_AUTHENTICATOR_KEY": """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAnME9k+VaxbUD2fGDgpKH
Ri6cE4T6HZzqWDpvtOShhoHSYQ6VlX0YnDQYwdDoTTK+XIBG2uS8W+3CsvpxjpHF
8Ny5xzxNGZTeqSn8A08BvoQ5cX7bnXOYUb4x2Pp/00WwaQseumUNP+ep/jCV+aqv
iWzOmX9p8zZGdFghvplbt9A173df4t6kICK11hUm14mpUtL/bCQ2xsUEmPGX+zw8
V1kynwJp2AaBuFVpkKDjHyHQJ+yotou01Vksp1kYoX21odjoZCivArEjuwzDEoHt
6WHPLnwvkBYouNA9jgR63mS1rW1PiloDlNNMFW1nR+AHjTfVSKKatnswO3JVLxYe
qwIDAQAB
-----END PUBLIC KEY-----""",
    "REMOTE_AUTHENTICATOR_URL": "http://plus:8000/api/v2/get-token/",
    "REMOTE_AUTHENTICATOR_UID": "aplus",
    "TRUSTING_REMOTES": {
         "http://gitmanager:8070": "gitmanager",
    },
    "DISABLE_LOGIN_CHECKS": False,
    "DISABLE_JWT_SIGNING": False,
}

# kate: space-indent on; indent-width 4;
# vim: set expandtab ts=4 sw=4:
