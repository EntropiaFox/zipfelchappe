
zipfelchappe
============

Zipfelchappe is a crowdfunding tool based on django and feincms.

An old campaign realised with zipfelchappe can be found here:

http://www.beiss-den-hai.ch/

Docs are here: https://zipfelchappe.readthedocs.org/

----
BUGS:

As in Django 1.8 ContentType are changed migrations will fail with: Error creating new content types.
http://stackoverflow.com/questions/29917442/error-creating-new-content-types-please-make-sure-contenttypes-is-migrated-befo

The removal of ContentType.name can be circumvented, for a new install, by running
python manage.py migrate auth
python manage.py migrate sites
python manage.py migrate
