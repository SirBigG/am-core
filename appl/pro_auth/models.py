# -*- coding: utf-8 -*-

from django.db import models
from django.contrib.auth.models import PermissionsMixin
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from appl.classifier.models import Location


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, phone1, password, **extra_fields):
        """
        Creates and saves a User with the given email and password.
        """
        if not email:
            raise ValueError('The given email must be set')
        if not phone1:
            raise ValueError('The given phone must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, phone1=phone1, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, phone1, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, phone1, password, **extra_fields)

    def create_superuser(self, email, phone1, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, phone1, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Model for all project users.

    Email, phone1 and password are required. Other fields are optional.
    """
    email = models.EmailField(
        unique=True,
        help_text=_('Required. You use it at every entrance to the site.'),
        error_messages={
                'unique': _("A user with that email already exists."),
                },
        verbose_name=_('user email'), )
    first_name = models.CharField(_('first name'), max_length=30, blank=True)
    last_name = models.CharField(_('last name'), max_length=30, blank=True)

    phone1 = models.CharField(max_length=25, verbose_name=_('main phone'))
    phone2 = models.CharField(max_length=25, blank=True, null=True,
                              verbose_name=_('extra phone'))
    phone3 = models.CharField(max_length=25, blank=True, null=True,
                              verbose_name=_('extra phone'))

    location = models.ForeignKey(Location, blank=True, null=True,
                                 verbose_name=_('user location'))
    birth_date = models.DateField(blank=True, null=True,
                                  verbose_name=_('date of birth'))

    is_staff = models.BooleanField(
        _('staff status'),
        default=False,
        help_text=_('Designates whether the user can log into this admin site.'),
    )
    is_active = models.BooleanField(
        _('active'),
        default=True,
        help_text=_(
            'Designates whether this user should be treated as active. '
            'Unselect this instead of deleting accounts.'
        ),
    )
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)

    avatar = models.ImageField(upload_to='/uploads/avatars/', blank=True,
                               verbose_name=_('avatar'))

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['phone1']

    class Meta:
        db_table = 'custom_user'
        verbose_name = _('custom user')
        verbose_name_plural = _('custom users')
        swappable = 'AUTH_USER_MODEL'

    def __unicode__(self):
        if self.first_name:
            return self.first_name
        return self.email

    def get_full_name(self):
        """
        Returns the first_name plus the last_name, with a space in between.
        """
        full_name = '%s %s' % (self.first_name, self.last_name)
        return full_name.strip()

    def get_short_name(self):
        """
        Returns the short name for the user.
        """
        return self.first_name

    def email_user(self, subject, message, from_email=None, **kwargs):
        """
        Sends an email to this User.
        """
        send_mail(subject, message, from_email, [self.email], **kwargs)

    backend = settings.AUTHENTICATION_BACKENDS
