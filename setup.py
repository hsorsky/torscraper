from setuptools import setup

setup(
    name='torscraper',
    description='Henry\'s tor scraper',
    version='0.1',
    packages=['torscraper'],
    install_requires=[
        'PySocks',
        'requests',
        'stem',
        'termcolor',
    ],
)