from distutils.core import setup

setup(
    name='django-harness',
    version='0.140404',
    author='Chris Wilson',
    author_email='support+django-harness@aptivate.org',
    packages=['django_harness'],
    url='http://github.com/aptivate/django-harness',
    license='LICENSE.txt',
    description='Functions to test Django and Django CMS applications',
    install_requires=[
        "django >= 1.5",
    ],
)
