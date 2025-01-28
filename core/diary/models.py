from datetime import date
from io import BytesIO

from ckeditor.fields import RichTextField
from django.core.files import File
from django.db import models
from django.urls import reverse
from PIL import Image

WIDTH = 350


class Diary(models.Model):
    user = models.ForeignKey("pro_auth.User", on_delete=models.SET_NULL, null=True)
    title = models.CharField(max_length=255, verbose_name="Заголовок")
    description = RichTextField(verbose_name="Короткий опис")
    public = models.BooleanField(default=False, verbose_name="Хочу щоб бачили всі")
    created = models.DateTimeField(auto_now_add=True)

    def get_profile_absolute_url(self):
        return reverse("pro_auth:profile-diary-detail", kwargs={"pk": self.pk})

    def get_absolute_url(self):
        return reverse("diary:detail", kwargs={"pk": self.pk})


class DiaryItem(models.Model):
    diary = models.ForeignKey(Diary, on_delete=models.CASCADE, related_name="diary_items")
    description = RichTextField(verbose_name="Опис")
    image = models.ImageField(upload_to="diaries/images", verbose_name="Фото", null=True, blank=True)
    date = models.DateField(default=date.today, verbose_name="Дата")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-date",)

    def save(self, *args, **kwargs):
        """Cut image before save."""
        if self.image:
            im = Image.open(BytesIO(self.image.read()))
            if im.mode != "RGB":
                im = im.convert("RGB")
            im = im.resize((WIDTH, int(float(im.size[1]) * float(WIDTH / float(im.size[0])))), Image.LANCZOS)
            output = BytesIO()
            im.save(output, format="JPEG", quality=85)
            self.image = File(output, self.image.name)
        super().save(*args, **kwargs)
