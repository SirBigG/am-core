import os
from PIL import Image
from io import BytesIO

from django.db import models
from django.core.files import File
from django.urls import reverse

from ckeditor.fields import RichTextField


WIDTH = 350


class Diary(models.Model):
    user = models.ForeignKey('pro_auth.User', on_delete=models.SET_NULL, null=True)
    title = models.CharField(max_length=255, verbose_name="Заголовок")
    description = RichTextField(verbose_name="Короткий опис")
    public = models.BooleanField(default=True, verbose_name="Хочу щоб бачили всі")
    created = models.DateTimeField(auto_now_add=True)

    def get_profile_absolute_url(self):
        return reverse('pro_auth:profile-diary-detail', kwargs={"pk": self.pk})


class DiaryItem(models.Model):
    diary = models.ForeignKey(Diary, on_delete=models.CASCADE)
    description = RichTextField(verbose_name="Опис")
    image = models.ImageField(upload_to='diaries/images', verbose_name="Фото")
    created = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        """Cut image before save."""
        if self.image:
            im = Image.open(BytesIO(self.image.read()))
            if im.mode != 'RGB':
                im = im.convert('RGB')
            im = im.resize((WIDTH, int((float(im.size[1]) * float(WIDTH / float(im.size[0]))))), Image.ANTIALIAS)
            output = BytesIO()
            im.save(output, format='JPEG', quality=85)
            self.image = File(output, self.image.name)
        super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        """Delete file of image after object deleting."""
        path = self.image.path
        super().delete(using=None, keep_parents=False)
        os.remove(path)
