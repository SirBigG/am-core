from django.db import models
from django.utils.translation import ugettext_lazy as _


class Category(models.Model):
    class Meta:
        db_table = 'category'
        verbose_name = _('category')
        verbose_name_plural = _('categories')

    category_field = models.CharField(
        max_length=20, verbose_name=_('category')
    )

    def __unicode__(self):
        return self.category_field


class PostPhoto(models.Model):
    class Meta:
        db_table = 'post_photo'
        verbose_name = _('post photo')
        verbose_name_plural = _('post photos')

    post_photo_field = models.ImageField(
        upload_to='uploads/post_photos/', verbose_name=_('post photo')
    )


class Post(models.Model):
    class Meta:
        db_table = 'post'
        verbose_name = _('post')
        verbose_name_plural = _('posts')

    post_category = models.ForeignKey(Category, verbose_name=_('category'), default=2)
    title = models.CharField(max_length=150, verbose_name=_('title'))
    date = models.DateTimeField(verbose_name=_('date'))
    text = models.TextField(verbose_name=_('text'))
    post_images = models.ManyToManyField(PostPhoto, verbose_name=_('post images'))

    def __unicode__(self):
        return self.title