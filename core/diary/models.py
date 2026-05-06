from datetime import date
from io import BytesIO

from ckeditor.fields import RichTextField
from django.core.files import File
from django.db import models
from django.urls import reverse
from PIL import Image

WIDTH = 350

PLANT_TYPE_CHOICES = [
    ("tomatoes", "Помідор"),
    ("cucumbers", "Огірок"),
    ("sweet_pepper", "Перець солодкий"),
    ("hot_pepper", "Перець гострий"),
    ("zucchini", "Кабачок"),
    ("eggplant", "Баклажан"),
    ("lettuce", "Салат"),
    ("radish", "Редиска"),
    ("basil", "Базилік"),
    ("parsley", "Петрушка"),
    ("strawberry", "Полуниця"),
    ("raspberry", "Малина"),
    ("blueberry", "Чорниця"),
    ("wild_strawberry", "Суниця"),
    ("dill", "Кріп"),
    ("green_onion", "Зелена цибуля"),
    ("mint", "М'ята"),
    ("arugula", "Рукола"),
    ("spinach", "Шпинат"),
]

PLANT_TYPE_EMOJIS = {
    "tomatoes": "🍅",
    "cucumbers": "🥒",
    "sweet_pepper": "🫑",
    "hot_pepper": "🌶️",
    "zucchini": "🥒",
    "eggplant": "🍆",
    "lettuce": "🥬",
    "carrot": "🥕",
    "radish": "🫜",
    "basil": "🌿",
    "parsley": "🌿",
    "dill": "🌿",
    "green_onion": "🧅",
    "mint": "🌿",
    "arugula": "🥬",
    "spinach": "🥬",
    "strawberry": "🍓",
    "raspberry": "🍓",
    "blueberry": "🫐",
    "wild_strawberry": "🍓",
}

DIARY_ITEM_ACTION_CHOICES = [
    ("watering", "💧 Підлив"),
    ("fertilizer", "🌿 Добриво"),
    ("photo", "📷 Фото"),
    ("note", "✏️ Нотатка"),
    ("planted", "🌱 Посаджено"),
    ("transplanted", "🪴 Пересаджено"),
    ("disease", "🤒 Хвороба"),
    ("pest", "🐛 Шкідник"),
    ("pruning", "✂️ Обрізка"),
    ("harvest", "🧺 Збір урожаю"),
    ("finished", "🏁 Завершити рослину"),
]

DIARY_PLANT_STATUS_CHOICES = [
    ("active", "Активна"),
    ("completed", "Завершена"),
]


class Diary(models.Model):
    user = models.ForeignKey("pro_auth.User", on_delete=models.SET_NULL, null=True)
    title = models.CharField(max_length=255, verbose_name="Заголовок")
    description = RichTextField(verbose_name="Короткий опис", blank=True, null=True)
    public = models.BooleanField(default=False, verbose_name="Хочу щоб бачили всі")
    is_archived = models.BooleanField(default=False, verbose_name="Архівований")
    plants = models.ManyToManyField(
        "Plant",
        blank=True,
        related_name="diaries",
        verbose_name="Рослини",
    )
    plant_type = models.CharField(
        max_length=50,
        choices=PLANT_TYPE_CHOICES,
        blank=True,
        default="",
        verbose_name="Вид рослини",
    )
    plant_date = models.DateField(default=date.today, verbose_name="Дата")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def get_profile_absolute_url(self):
        return reverse("pro_auth:profile-diary-detail", kwargs={"pk": self.pk})

    def get_absolute_url(self):
        return reverse("diary:detail", kwargs={"pk": self.pk})

    @property
    def plant_emoji(self):
        primary_plant = self.active_plants[0] if self.active_plants else None
        if primary_plant:
            return primary_plant.plant_emoji
        return PLANT_TYPE_EMOJIS.get(self.plant_type, "🌱")

    @property
    def plant_summary(self):
        plants = self.active_plants
        if plants:
            return ", ".join(plant.display_name for plant in plants)
        if self.plant_type:
            return f"{self.get_plant_type_display()} - {self.title}"
        return self.title

    @property
    def active_plants(self):
        if hasattr(self, "active_diary_plants"):
            return list(self.active_diary_plants)
        return list(self.plants.filter(status="active"))


class Plant(models.Model):
    user = models.ForeignKey("pro_auth.User", on_delete=models.SET_NULL, null=True, related_name="plants")
    category = models.ForeignKey(
        "classifier.Category",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="plants",
        verbose_name="Категорія",
    )
    title = models.CharField(max_length=255, blank=True, verbose_name="Назва")
    variety = models.CharField(max_length=255, blank=True, verbose_name="Сорт")
    description = RichTextField(blank=True, verbose_name="Опис")
    plant_date = models.DateField(default=date.today, verbose_name="Дата посадки")
    status = models.CharField(
        max_length=16,
        choices=DIARY_PLANT_STATUS_CHOICES,
        default="active",
        verbose_name="Статус рослини",
    )
    completed_at = models.DateField(null=True, blank=True, verbose_name="Дата завершення")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created", "id")

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        parts = []
        if self.category_id:
            parts.append(self.category.value)
        if self.variety:
            parts.append(self.variety)
        if self.title:
            parts.append(self.title)
        return " - ".join(parts) or "Рослина"

    @property
    def plant_emoji(self):
        if self.category_id:
            return PLANT_TYPE_EMOJIS.get(self.category.slug, "🌱")
        return "🌱"


class DiaryItem(models.Model):
    diary = models.ForeignKey(Diary, on_delete=models.CASCADE, related_name="diary_items")
    action_type = models.CharField(
        max_length=32,
        choices=DIARY_ITEM_ACTION_CHOICES,
        blank=True,
        default="",
        verbose_name="Оберіть швидку дію",
    )
    apply_to_all = models.BooleanField(default=True, verbose_name="Застосувати до всіх активних рослин")
    plants = models.ManyToManyField(
        Plant,
        blank=True,
        related_name="diary_items",
        verbose_name="Рослини",
    )
    description = RichTextField(blank=True, verbose_name="Опис")
    image = models.ImageField(upload_to="diaries/images", verbose_name="Фото", null=True, blank=True)
    date = models.DateField(default=date.today, verbose_name="Дата")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-date", "-created")

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
