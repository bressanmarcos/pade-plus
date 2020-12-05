
import os
os.sys.path.insert(0, os.path.join(os.getcwd(), 'pade'))
from __version__ import __version__

from setuptools import setup

with open("README.md", "r", encoding='UTF-8') as fh:
    long_description = fh.read()

setup(name='pade-plus',
      version=__version__,
      description='An extension to PADE to allow sync-like asynchronous programming in FIPA interaction protocols.',
      long_description=long_description,
      long_description_content_type="text/markdown",
      author='Marcos Bressan',
      author_email='bressanmarcos@alu.ufc.br',
      license='MIT',
      keywords='multiagent distributed systems',
      packages=['pade.behaviours', 'pade.plus'],
      install_requires=[
          'pade'
      ],
      classifiers=[
              'Intended Audience :: Developers',
              'Topic :: Software Development :: Build Tools',
              'License :: OSI Approved :: MIT License',
              'Operating System :: OS Independent',
              'Programming Language :: Python :: 3',
              'Programming Language :: Python :: 3.7',
      ],)
