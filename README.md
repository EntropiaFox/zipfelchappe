zipfelchappe
============

Zipfelchappe is a crowdfunding tool based on django and feincms.

An old campaign realised with zipfelchappe can be found here:

http://www.beiss-den-hai.ch/

Docs are here: https://zipfelchappe.readthedocs.org/

Django 1.8, FeinCMS 1.12
========================
As in Django 1.8 ContentType are changed migrations will fail with: Error creating new content types.
http://stackoverflow.com/questions/29917442/error-creating-new-content-types-please-make-sure-contenttypes-is-migrated-befo

The removal of ContentType.name can be circumvented, for a new install, by running
`python manage.py migrate auth`
`python manage.py migrate sites`
`python manage.py migrate`


After that you'll need an admin user and a Page of ApplicationContent type so you can use the default
landingpage at /projects

![Setup Project Landing page](docs/_static/landingpage.png?raw=true "Setup Project Landing page")

A small demo is available at https://fundraiser.formatics.nl