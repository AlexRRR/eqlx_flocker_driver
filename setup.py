from setuptools import setup, find_packages
import codecs 
from os import path

try:
    with codecs.open('DESCRIPTION.rst', encoding='utf-8') as f:
        long_description = f.read()
except:
    long_description = ''

setup(
    name='eqlx_flocker_plugin',
    version='0.1',
    description='Dell Equallogic Flocker Driver',
    long_description=long_description,
    author='Alejandro Ramirez',
    author_email='alexrrr@hotmail.com',
    url='https://github.com/AlexRRR/eqlx_flocker_driver.git',
    license='Apache 2.0',

    classifiers=[

    'Development Status :: 4 - Beta',

    'Intended Audience :: System Administrators',
    'Intended Audience :: Developers',
    'Topic :: Software Development :: Libraries :: Python Modules',

    'License :: OSI Approved :: Apache Software License',

    # Python versions supported
    'Programming Language :: Python :: 2.7',
    ],

    keywords='backend, plugin, flocker, docker, python',
    packages=find_packages(exclude=['test*']),
)
