#!/usr/bin/env python

from setuptools import setup, find_packages
import paypaladaptive

setup(
    name='django-paypal-adaptive',
    version=".".join(map(str, paypaladaptive.__version__)),
    author='Greg McGuire',
    author_email='greg@buzzcar.com',
    maintainer='Greg McGuire',
    maintainer_email="greg@buzzcar.com",
    url='http://github.com/gmcguire/django-paypal-adaptive',
    install_requires=[
        'Django>=1.4.3',
        'python-dateutil==2.1',
        '-e hg+https://bitbucket.org/acoobe/python-money/@edf852242ce422a7320c'
        '5fc95ceb01c0d38e7647#egg=python_money-dev'
    ],
    description = 'A pluggable Django application for integrating PayPal'
                  'Adaptive Payments',
    packages=find_packages(),
    include_package_data=True,
    classifiers=[
        "Framework :: Django",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Operating System :: OS Independent",
        "Topic :: Software Development"
    ],
)