import sys

from django.conf import settings
from django.test.simple import DjangoTestSuiteRunner

settings.configure(
    DEBUG=True,
    DATABASES={
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
        }
    },
    ROOT_URLCONF='myapp.urls',
    INSTALLED_APPS=('django.contrib.auth',
                    'django.contrib.contenttypes',
                    'django.contrib.sessions',
                    'django.contrib.admin',
                    'paypaladaptive'))


test_runner = DjangoTestSuiteRunner(verbosity=1)
failures = test_runner.run_tests(['paypaladaptive'])

if failures:
    sys.exit(failures)