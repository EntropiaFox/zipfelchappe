from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from django.db import models
from django.db.models import signals, Sum

from django.utils.translation import ugettext_lazy as _
from django.utils.translation import get_language
from django.utils import timezone

from feincms.models import Base
from feincms.management.checker import check_database_schema as check_db_schema
from feincms.utils.queryset_transform import TransformQuerySet
from feincms.content.application import models as app_models

from .app_settings import BACKER_MODEL, CURRENCIES
from .base import CreateUpdateModel
from .fields import CurrencyField
from .utils import use_default_backer_model

CURRENCY_CHOICES = list(((cur, cur) for cur in CURRENCIES))


class TranslatedMixin(object):
    @property
    def translated(self):
        if hasattr(self, '_translation'):
            return self._translation
        else:
            filters = {'translation_of': self}
            if hasattr(self, 'project'):
                filters['translation__lang'] = get_language()
            else:
                filters['lang'] = get_language()
            try:
                self._translation = self.translations.get(**filters)
            except:
                self._translation = self

            return self._translation


class BackerBase(models.Model):

    user = models.ForeignKey(User, blank=True, null=True, unique=True)

    _first_name = models.CharField(_('first name'), max_length=30, blank=True)

    _last_name = models.CharField(_('last name'), max_length=30, blank=True)

    _email = models.EmailField(_('e-mail address'), blank=True)

    class Meta:
        verbose_name = _('backer')
        verbose_name_plural = _('backers')
        abstract = True

    def __unicode__(self):
        return self.full_name

    @property
    def first_name(self):
        return self.user.first_name if self.user else self._first_name

    @property
    def last_name(self):
        return self.user.last_name if self.user else self._last_name

    @property
    def email(self):
        return self.user.email if self.user else self._email

    @property
    def full_name(self):
        if self.first_name or self.last_name:
            return u'%s %s' % (self.first_name, self.last_name)
        else:
            return unicode(self.user)

if use_default_backer_model():
    class Backer(BackerBase):
        pass


class Pledge(CreateUpdateModel, TranslatedMixin):

    UNAUTHORIZED = 10
    AUTHORIZED = 20
    PAID = 30

    STATUS_CHOICES = (
        (UNAUTHORIZED, _('Unauthorized')),
        (AUTHORIZED, _('Authorized')),
        (PAID, _('Paid')),
    )

    backer = models.ForeignKey(BACKER_MODEL, verbose_name=_('backer'),
        related_name='pledges', blank=True, null=True)

    project = models.ForeignKey('Project', verbose_name=_('project'),
        related_name='pledges')

    amount = CurrencyField(_('amount'), max_digits=10, decimal_places=2)

    currency = models.CharField(_('currency'), max_length=3,
        choices=CURRENCY_CHOICES, editable=False, default=CURRENCY_CHOICES[0])

    reward = models.ForeignKey('Reward', blank=True, null=True,
        related_name='pledges')

    anonymously = models.BooleanField(_('anonymously'),
        help_text=_('You will not appear in the backer list'))

    status = models.PositiveIntegerField(_('status'), choices=STATUS_CHOICES,
            default=UNAUTHORIZED)

    class Meta:
        verbose_name = _('pledge')
        verbose_name_plural = _('pledges')

    def __unicode__(self):
        return u'Pledge of %d %s from %s to %s' % \
            (self.amount, self.currency, self.backer, self.project)

    def save(self, *args, **kwargs):
        self.currency = self.project.currency
        super(Pledge, self).save(*args, **kwargs)


class Reward(CreateUpdateModel, TranslatedMixin):

    project = models.ForeignKey('Project', verbose_name=_('project'),
        related_name='rewards')

    minimum = CurrencyField(_('minimum'), max_digits=10, decimal_places=2,
        help_text=_('How much does one have to donate to receive this?'))

    description = models.TextField(_('description'), blank=True)

    quantity = models.IntegerField(_('quantity'), blank=True, null=True,
        help_text=_('How many times can this award be given away? Leave ' +
            'empty to means unlimited'))

    class Meta:
        verbose_name = _('reward')
        verbose_name_plural = _('rewards')
        ordering = ['minimum']

    def __unicode__(self):
        return u'%s on %s (%d)' % (self.minimum, self.project, self.pk)

    def clean(self):
        if self.id and self.quantity and self.quantity < self.awarded:
            raise ValidationError(_('Cannot reduce quantity to a lower value ' +
                'than what was already promised to backers'))

    @property
    def reserved(self):
        return self.pledges.count()

    @property
    def awarded(self):
        return self.pledges.filter(status__gte=Pledge.AUTHORIZED).count()

    @property
    def available(self):
        return self.quantity - self.awarded

    @property
    def is_available(self):
        if not self.quantity:
            return True
        else:
            return self.available > 0


class Category(CreateUpdateModel):

    title = models.CharField(_('title'), max_length=100)

    slug = models.SlugField(_('slug'), unique=True)

    ordering = models.SmallIntegerField(_('ordering'), default=0)

    class Meta:
        verbose_name = _('category')
        verbose_name_plural = _('categories')
        ordering = ['ordering']

    def __unicode__(self):
        return self.title

    @app_models.permalink
    def get_absolute_url(self):
        return ('zipfelchappe_project_category_list', 'zipfelchappe.urls',
             (self.slug,)
        )

    @property
    def project_count(self):
        return self.projects.count()


class Update(CreateUpdateModel, TranslatedMixin):

    STATUS_DRAFT = 'draft'
    STATUS_PUBLISHED = 'published'

    STATUS_CHOICES = (
        (STATUS_DRAFT, _('Draft')),
        (STATUS_PUBLISHED, _('Published')),
    )

    project = models.ForeignKey('Project', verbose_name=_('project'),
        related_name='updates')

    title = models.CharField(_('title'), max_length=100)

    status = models.CharField(_('status'), max_length=20,
        choices=STATUS_CHOICES, default='draft')
    mails_sent = models.BooleanField(editable=False)

    def update_upload_to(instance, filename):
        return (u'projects/%s/updates/%s' % (instance.project.slug, filename)).lower()

    image = models.ImageField(_('image'), blank=True, null=True,
        upload_to=update_upload_to)

    external = models.URLField(_('external content'), blank=True, null=True,
         help_text=_('Check http://embed.ly/providers for more details'),
    )

    content = models.TextField(_('content'), blank=True)

    attachment = models.FileField(_('attachment'), blank=True, null=True,
        upload_to=update_upload_to)

    class Meta:
        verbose_name = _('update')
        verbose_name_plural = _('updates')
        ordering = ('-created',)

    def __unicode__(self):
        return self.title

    @app_models.permalink
    def get_absolute_url(self):
        return ('zipfelchappe_update_detail', 'zipfelchappe.urls',
            (self.project.slug, self.pk)
        )

    @property
    def number(self):
        if hasattr(self, 'num'):
            return self.num
        updates = self.project.updates.filter(status=Update.STATUS_PUBLISHED)
        for index, item in enumerate(reversed(updates)):
            if item == self:
                self.num = index + 1
                return self.num
        return None


class MailTemplate(CreateUpdateModel, TranslatedMixin):

    ACTION_THANKYOU = 'thankyou'

    ACTION_CHOICES = (
        (ACTION_THANKYOU, _('Thank you')),
    )

    project = models.ForeignKey('Project', related_name='mail_templates')

    action = models.CharField(_('action'), max_length=30,
        choices=ACTION_CHOICES, default=ACTION_THANKYOU)

    subject = models.CharField(_('subject'), max_length=200)

    template = models.TextField(_('template'))

    class Meta:
        verbose_name = _('mail')
        verbose_name_plural = _('mails')
        unique_together = (('project', 'action'),)

    def __unicode__(self):
        return '%s mail for %s' % (self.action, self.project)


class ProjectManager(models.Manager):

    def get_query_set(self):
        return TransformQuerySet(self.model, using=self._db)

    def online(self):
        return self.filter(start__lte=timezone.now)

    def funding(self):
        return self.online().filter(end__gte=timezone.now)


class Project(Base, TranslatedMixin):

    title = models.CharField(_('title'), max_length=100)

    slug = models.SlugField(_('slug'), unique=True)

    position = models.IntegerField('#')

    goal = CurrencyField(_('goal'), max_digits=10, decimal_places=2,
        help_text=_('Amount you want to raise'))

    currency = models.CharField(_('currency'), max_length=3,
        choices=CURRENCY_CHOICES, default=CURRENCY_CHOICES[0])

    start = models.DateTimeField(_('start'),
        help_text=_('Date the project will be online'))

    end = models.DateTimeField(_('end'),
        help_text=_('Until when money is raised'))

    backers = models.ManyToManyField(BACKER_MODEL, verbose_name=_('backers'),
        through='Pledge')

    def teaser_img_upload_to(instance, filename):
        return (u'projects/%s/%s' % (instance.slug, filename)).lower()

    teaser_image = models.ImageField(_('image'), blank=True, null=True,
        upload_to=teaser_img_upload_to)

    teaser_text = models.TextField(_('text'), blank=True)

    objects = ProjectManager()

    class Meta:
        verbose_name = _('project')
        verbose_name_plural = _('projects')
        ordering = ('position',)
        get_latest_by = 'end'

    def save(self, *args, **kwargs):
        model = self.__class__

        if self.position is None:
            try:
                last = model.objects.order_by('-position')[0]
                self.position = last.position + 1
            except IndexError:
                self.position = 0

        return super(Project, self).save(*args, **kwargs)

    def __unicode__(self):
        return self.title

    def clean(self):
        if self.start and self.end and self.start > self.end:
            raise ValidationError(_('Start must be before end'))

        if self.start and self.end and \
           self.end - self.start > timedelta(days=120):
            raise ValidationError(_('Project length can be max. 120 days'))

        if self.pk:
            dbinst = Project.objects.get(pk=self.pk)

            if self.has_pledges and self.currency != dbinst.currency:
                raise ValidationError(_('You cannot change the currency anymore'
                    ' once your project has been backed by users'))

            if self.has_pledges and self.end != dbinst.end:
                raise ValidationError(_('You cannot change the end date anymore'
                    ' once your project has been backed by users'))

    @app_models.permalink
    def get_absolute_url(self):
        return ('zipfelchappe_project_detail', 'zipfelchappe.urls',
            (self.slug,)
        )

    @classmethod
    def create_content_type(cls, model, *args, **kwargs):
        # Registers content type for translations too
        super(Project, cls).create_content_type(model, *args, **kwargs)
        if 'zipfelchappe.translations' in settings.INSTALLED_APPS:
            from zipfelchappe.translations.models import ProjectTranslation
            kwargs['class_name'] = 'Translated%s' % model._meta.object_name
            ProjectTranslation.create_content_type(model, *args, **kwargs)

    @classmethod
    def register_regions(cls, *args, **kwargs):
        # Register regions for translations too
        super(Project, cls).register_regions(*args, **kwargs)
        if 'zipfelchappe.translations' in settings.INSTALLED_APPS:
            from zipfelchappe.translations.models import ProjectTranslation
            ProjectTranslation.register_regions(*args, **kwargs)

    @property
    def authorized_pledges(self):
        return self.pledges.filter(status__gte=Pledge.AUTHORIZED)

    @property
    def has_pledges(self):
        return self.pledges.count() > 0

    @property
    def achieved(self):
        amount = self.authorized_pledges.aggregate(Sum('amount'))
        return amount['amount__sum'] or 0

    @property
    def percent(self):
        return int((self.achieved * 100) / self.goal)

    @property
    def goal_display(self):
        return u'%s %s' % (int(self.goal), self.currency)

    @property
    def achieved_display(self):
        return u'%d %s (%d%%)' % (self.achieved, self.currency, self.percent)

    @property
    def is_active(self):
        return timezone.now() < self.end

    @property
    def less_than_24_hours(project):
        return project.end - timezone.now() < timedelta(hours=24)

    @property
    def is_financed(self):
        return self.achieved >= self.goal

    @property
    def update_count(self):
        return self.updates.filter(status='published').count()

    @property
    def public_pledges(self):
        return self.pledges.filter(
            status__gte=Pledge.AUTHORIZED,
            anonymously=False
        )

    @classmethod
    def register_extension(cls, register_fn):
        register_fn(cls, ProjectAdmin)


# Zipfelchappe has two fixed regions which cannot be configured a.t.m.
# This may change in future versions but suffices our needs for now
Project.register_regions(
    ('main', _('Content')),
    ('thankyou', _('Thank you')),
)

signals.post_syncdb.connect(check_db_schema(Project, __name__), weak=False)

