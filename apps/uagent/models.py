from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _

from apps.main_app.models import Region
# Create your models here.
class UserInformation(models.Model):
    class Meta:
        db_table = "user_information"
        verbose_name = _('user information')
        verbose_name_plural = _('user information')

    profile = models.OneToOneField(User)
    avatar = models.ImageField(
        upload_to='uploads/avatars/', verbose_name=_('avatar'),
        blank=True
    )
    location = models.ForeignKey(Region, verbose_name=_('location'),default=2)
    phone = models.IntegerField(unique=True,verbose_name=_('phone'), blank=True)
    birth_date = models.DateField(verbose_name=_('birth date'), blank=True)
    about = models.TextField(verbose_name=_('about you'), blank=True)
    breed = models.TextField(verbose_name=_('pigeons breed'), blank=True)

    def __unicode__(self):
        return self.about