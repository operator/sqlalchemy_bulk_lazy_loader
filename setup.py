from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='sqlalchemy_bulk_lazy_loader',
    version='0.9.0',
    description='A Bulk Lazy Loader for Sqlalchemy that solves the n + 1 loading problem',
    long_description=long_description,
    url='https://github.com/operator/sqlalchemy_bulk_lazy_loader',
    author='Operator Inc',
    author_email='chanind@operator.com',
    license='MIT',
    classifiers=[
        'Intended Audience :: Developers',
        'Topic :: Software Development :: ORM',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
    ],
    keywords='sqlalchemy orm lazyload joinedload subqueryload',
    py_modules=["sqlalchemy_bulk_lazy_loader"],
    install_requires=['sqlalchemy'],
)