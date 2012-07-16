from datetime import datetime

from django.contrib import admin
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import signals, Q, Sum
from django.utils.translation import ugettext_lazy as _

from feincms.admin import item_editor
from feincms.models import Base
from feincms.management.checker import check_database_schema as check_db_schema
from feincms.utils.queryset_transform import TransformQuerySet

from .app_settings import BACKER_MODEL, CURRENCIES
from .base import CreateUpdateModel
from .fields import CurrencyField
from .utils import use_default_backer_model
from .widgets import AdminImageWidget

CURRENCY_CHOICES = list(((cur, cur) for cur in CURRENCIES))

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
        return u'%s %s' % (self.first_name, self.last_name)

if use_default_backer_model():
    class Backer(BackerBase):
        pass

class Pledge(CreateUpdateModel):

    UNAUTHORIZED = 10
    AUTHORIZED = 20
    PAID = 30

    STATUS_CHOICES = (
        (UNAUTHORIZED, _('Unauthorizded')),
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
        related_name = 'pledges')

    anonymously = models.BooleanField(_('anonymously'))

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


class Reward(CreateUpdateModel):

    project = models.ForeignKey('Project', verbose_name=_('project'),
        related_name='rewards')

    title = models.CharField(_('title'), max_length=100)

    minimum = CurrencyField(_('minimum'), max_digits=10, decimal_places=2,
        help_text = _('How much does one have to donate to receive this?'))

    description = models.TextField(_('description'), blank=True)

    quantity = models.IntegerField(_('quantity'), blank=True, null=True,
        help_text = _('How many times can this award be give away? Leave ' +
                      'empty to means unlimited'))

    class Meta:
        verbose_name = _('reward')
        verbose_name_plural = _('rewards')
        ordering = ['minimum',]

    def __unicode__(self):
        return self.title

    def clean(self):
        if self.quantity != None and self.quantity < self.awarded:
            raise ValidationError(_('Cannot reduce quantiy to a lower value ' +
                'than it was allready promised to backers'))

    @property
    def awarded(self):
        return self.pledges.filter(status=Pledge.AUTHORIZED).count()

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

    @models.permalink
    def get_absolute_url(self):
        return ('zipfelchappe_project_category_list', (self.slug,))

    @property
    def project_count(self):
        return self.projects.count()


class ProjectManager(models.Manager):

    def get_query_set(self):
        return TransformQuerySet(self.model, using=self._db)

    def online(self):
        return self.filter(start__lte=datetime.now)

    def funding(self):
        return self.online().filter(end__gte=datetime.now)


class Project(Base):

    title = models.CharField(_('title'), max_length=100)

    slug = models.SlugField(_('slug'), unique=True)

    author = models.ForeignKey(User, blank=True, null=True)

    goal = CurrencyField(_('goal'), max_digits=10, decimal_places=2,
        help_text = _('Amount you want to raise'))

    currency = models.CharField(_('currency'), max_length=3,
        choices=CURRENCY_CHOICES, default=CURRENCY_CHOICES[0])

    start = models.DateTimeField(_('start'),
        help_text=_('Date the project will be online'))

    end = models.DateTimeField(_('end'),
        help_text=_('Until when money is raised'))

    categories = models.ManyToManyField(Category, verbose_name=_('categories'),
        related_name='projects', null=True, blank=True)

    backers = models.ManyToManyField(BACKER_MODEL, verbose_name=_('backers'),
        through='Pledge')

    def teaser_img_upload_to(instance, filename):
        return (u'projects/%s/%s' % (instance.slug, filename)).lower()

    teaser_image = models.ImageField(_('image'), blank=True, null=True,
        upload_to = teaser_img_upload_to)

    teaser_text = models.TextField(_('text'), blank=True)


    objects = ProjectManager()

    class Meta:
        verbose_name = _('project')
        verbose_name_plural = _('projects')
        get_latest_by = 'end'


    def __unicode__(self):
        return self.title

    def clean(self):
        if self.start > self.end:
            raise ValidationError(_('Start must be before end'))

        if self.pk:
            dbinst = Project.objects.get(pk=self.pk)

            if dbinst.has_pledges and self.currency != dbinst.currency:
                raise ValidationError(_('Cannot change currency with pledges!'))

    @models.permalink
    def get_absolute_url(self):
        return ('zipfelchappe_project_detail', (self.slug,))

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
        return u'%s %s' % (self.goal, self.currency)

    @property
    def achieved_display(self):
        return u'%d %s (%d%%)' % (self.achieved, self.currency, self.percent)

    @property
    def is_financed(self):
        return self.achieved > self.goal

    @classmethod
    def register_extension(cls, register_fn):
        register_fn(cls, ProjectAdmin)


signals.post_syncdb.connect(check_db_schema(Project, __name__), weak=False)


class RewardInlineAdmin(admin.StackedInline):
    model = Reward
    extra = 0
    feincms_inline = True
    fieldsets = [
        [None, {
            'fields': [
                'title',
                ('minimum', 'quantity'),
                'description',
            ]
        }]
    ]

class PledgeInlineAdmin(admin.TabularInline):
    model = Pledge
    extra = 0
    raw_id_fields = ('backer','project')
    feincms_inline = True


class ProjectAdmin(item_editor.ItemEditor):
    inlines = [RewardInlineAdmin, PledgeInlineAdmin]
    date_hierarchy = 'end'
    list_display = ['title', 'goal']
    search_fields = ['title', 'slug']
    readonly_fields = ('achieved_pretty',)
    raw_id_fields = ('author',)
    filter_horizontal = ['categories']
    prepopulated_fields = {
        'slug': ('title',),
        }

    formfield_overrides = {
        models.ImageField: {'widget': AdminImageWidget},
    }

    fieldset_insertion_index = 1
    fieldsets = [
        [None, {
            'fields': [
                ('title', 'slug'),
                ('goal', 'currency', 'achieved_pretty'),
                ('start', 'end'),
                'author',
            ]
        }],
        [_('teaser'), {
            'fields': [('teaser_image', 'teaser_text')],
            'classes': ['feincms_inline'],
        }],
        [_('categories'), {
            'fields': ['categories'],
            'classes': ['feincms_inline'],
        }],
        item_editor.FEINCMS_CONTENT_FIELDSET,
    ]

    def achieved_pretty(self, p):
        if p.id:
            return u'%d %s (%d%%)' % (p.achieved, p.currency, p.percent)
        else:
            return u'unknown'
    achieved_pretty.short_description = _('achieved')

    class Media:
        css = { "all" : (
            "zipfelchappe/css/project_admin.css",
            "zipfelchappe/css/feincms_extended_inlines.css",
            "zipfelchappe/css/admin_hide_original.css",
        )}
