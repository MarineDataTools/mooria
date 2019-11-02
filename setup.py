from setuptools import setup, find_packages
import os

ROOT_DIR='mooria'
with open(os.path.join(ROOT_DIR, 'VERSION')) as version_file:
    version = version_file.read().strip()


# read the contents of your README file
this_directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(this_directory, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()
    
setup(name='mooria',
      version=version,
      description='Mooring assistant, tool to design and create metadata for marine moorings',
      long_description=long_description,
      long_description_content_type='text/x-rst',            
      url='https://github.com/MarineDataTools/mooria',
      author='Peter Holtermann',
      author_email='peter.holtermann@io-warnemuende.de',
      license='GPLv03',
      packages=find_packages(),
      scripts = [],
      entry_points={ 'console_scripts': ['mooria=mooria.mooria:main']},      
      package_data = {'':['VERSION','devices/*.yaml']},
      #package_data = {'':['VERSION','devices/iow_stations.yaml','ships/ships.yaml']},
      install_requires=[ 'pyaml','geojson'],
      zip_safe=False)


