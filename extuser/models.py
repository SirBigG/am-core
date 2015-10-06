#-*- coding: utf-8 -*-

from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.contrib.auth.models import BaseUserManager
from django.db import models
from django.utils.translation import ugettext_lazy as _

#from main_app.models import Region

class UserManager(BaseUserManager):

    def create_user(self, email, password=None):
        if not email:
            raise ValueError(_('Email must be specified.'))

        user = self.model(
            email=UserManager.normalize_email(email),
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password):
        user = self.create_user(email, password)
        user.is_admin = True
        user.is_superuser = True
        user.save(using=self._db)
        return user


class ExtUser(AbstractBaseUser, PermissionsMixin):

    email = models.EmailField(
        _('Email'),
        max_length=255,
        unique=True,
        db_index=True
    )
    avatar = models.ImageField(
        _('Avatar'),
        blank=True,
        null=True,
        upload_to="uploads/avatars"
    )
    firstname = models.CharField(
        _('First_name'),
        max_length=40,
        null=True,
        blank=True
    )
    lastname = models.CharField(
        _('Last name'),
        max_length=40,
        null=True,
        blank=True
    )
    middlename = models.CharField(
        _('Middle name'),
        max_length=40,
        null=True,
        blank=True
    )
    date_of_birth = models.DateField(
        _('Date of birth'),
        null=True,
        blank=True
    )
    #location = models.ForeignKey(
    #    Region,
    #    _('location')
   # )
    about = models.TextField(
        verbose_name=_('About you'),
        blank=True
    )
    breed = models.TextField(
        verbose_name=_('Pigeons breed'),
        blank=True
    )
    register_date = models.DateField(
        _('Register date'),
        auto_now_add=True
    )
    is_active = models.BooleanField(
        _('Is active'),
        default=True
    )
    is_admin = models.BooleanField(
        _('Is superuser'),
        default=False
    )

    # Этот метод обязательно должен быть определён
    def get_full_name(self):
        return self.email

    # Требуется для админки
    @property
    def is_staff(self):
        return self.is_admin

    def get_short_name(self):
        return self.email

    def __str__(self):
        return self.email

    def has_perm(self, perm, obj=None):
        return True

    def has_module_perms(self, app_label):
        return True

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')
