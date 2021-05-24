# -*- coding: utf-8 -*-
"""
setuptools>=40.1.0
"""
from setuptools import setup, find_packages
#from codecs import open
import os
import re

root_dir = os.path.abspath(os.path.dirname(__file__))

def filetext(path):
    text = ""
    with open(os.path.join(root_dir, path), "r", encoding="utf-8") as fi:
        text = fi.read()
    return text

def version(text):
    m = re.search("__version__\\s+=\\s+'([^']+)'", text)
    if m:
        return m.group(1)
    raise ValueError("バージョン番号がありません")

#
#
#
package_name = "machaon"

version = version(filetext("machaon/__init__.py"))
licence = filetext("LICENSE")
requirements = [x.strip() for x in filetext("REQUIREMENTS.txt").splitlines()]
test_requirements = [x.strip() for x in filetext("TEST-REQUIREMENTS.txt").splitlines()]
long_description = filetext("README.rst") + "\n" + filetext("HISTORY.rst")


setup(
    name=package_name,
    version=version,
    
    packages=find_packages(exclude=['tests', 'tests.*']),
    package_data={"machaon" : ["configs/*.*", "configs/osx/*.*"]},
    
    license=license,
    
    install_requires=requirements,
    tests_require=test_requirements,
    test_suite="tests",
    
    author='Goro Sakata',
    author_email='gorosakata@ya.ru',
    url='',
    
    description='A small framework for interactive CLI-like application.',
    long_description=long_description,
    keywords='cli',

    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)




