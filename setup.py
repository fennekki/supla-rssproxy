from setuptools import setup, find_packages
from codecs import open
from os import path

setup_dir = path.abspath(path.dirname(__file__))

with open(path.join(setup_dir, "README.md"), encoding='utf-8') as f:
    long_description = f.read()

# Get __version__ and __url__
with open(path.join(setup_dir, 'supla_rssproxy/__init__.py')) as f:
    exec(f.read())

setup(
    name='supla-rssproxy',
    version=__version__,

    description='A tool for downloading podcasts from Supla via RSS',
    long_description=long_description,
    url=__url__,

    author='fennekki',

    license='BSD 2-clause',
    classifiers=[
        'Environment :: Console',
        'License :: OSI Approved :: BSD License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.5'
    ],

    keywords='',

    packages=find_packages(exclude=['tests']),

    install_requires=[
    ],

    package_data={},
    data_files=[],

    entry_points={
        'console_scripts': [
            'supla-rssproxy=supla_rssproxy.main:main'
        ]
    }
)
