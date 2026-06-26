from datetime import date
from decimal import Decimal
from io import BytesIO

from ckeditor.fields import RichTextField
from django.core.validators import MaxValueValidator, MinValueValidator
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

HARVEST_UNIT_CHOICES = [
    ("kg", "кг"),
    ("g", "г"),
    ("pcs", "шт"),
    ("bunch", "пучок"),
]

PLANNER_AREA_TYPE_CHOICES = [
    ("bed", "Грядка"),
    ("greenhouse", "Теплиця"),
    ("field", "Поле"),
    ("garden", "Город"),
    ("other", "Інша зона"),
]

PLANNER_PLANTING_MODE_CHOICES = [
    ("exact", "Точна кількість"),
    ("approximate", "Приблизна кількість"),
    ("rows", "Рядами"),
    ("area", "За площею"),
    ("broadcast", "Суцільний посів"),
    ("unknown", "Без підрахунку"),
]

PLANNER_PLANTING_STATUS_CHOICES = [
    ("planned", "Заплановано"),
    ("planted", "Посаджено"),
    ("growing", "Росте"),
    ("harvest", "Збір урожаю"),
    ("completed", "Завершено"),
]


class Planner(models.Model):
    user = models.ForeignKey(
        "pro_auth.User",
        on_delete=models.CASCADE,
        related_name="planners",
        verbose_name="Користувач",
    )
    title = models.CharField(max_length=255, default="Моя ділянка", verbose_name="Назва")
    width_m = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default="20.00",
        validators=[MinValueValidator(Decimal("1.00"))],
        verbose_name="Ширина, м",
    )
    height_m = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default="12.00",
        validators=[MinValueValidator(Decimal("1.00"))],
        verbose_name="Довжина, м",
    )
    grid_step_m = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default="0.50",
        validators=[MinValueValidator(Decimal("0.10"))],
        verbose_name="Крок сітки, м",
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated", "-id")

    def __str__(self):
        return self.title


class PlannerArea(models.Model):
    planner = models.ForeignKey(
        Planner,
        on_delete=models.CASCADE,
        related_name="areas",
        verbose_name="Планер",
    )
    diary = models.OneToOneField(
        "Diary",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planner_area",
        verbose_name="Щоденник",
    )
    title = models.CharField(max_length=255, verbose_name="Назва")
    area_type = models.CharField(
        max_length=24,
        choices=PLANNER_AREA_TYPE_CHOICES,
        default="bed",
        verbose_name="Тип зони",
    )
    x_m = models.DecimalField(max_digits=8, decimal_places=2, default="0.00", verbose_name="X, м")
    y_m = models.DecimalField(max_digits=8, decimal_places=2, default="0.00", verbose_name="Y, м")
    width_m = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default="4.00",
        validators=[MinValueValidator(Decimal("0.50"))],
        verbose_name="Ширина, м",
    )
    height_m = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default="1.20",
        validators=[MinValueValidator(Decimal("0.50"))],
        verbose_name="Довжина, м",
    )
    color = models.CharField(max_length=16, default="#69a85f", verbose_name="Колір")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created", "id")

    def __str__(self):
        return self.title

    @property
    def area_m2(self):
        return self.width_m * self.height_m


class PlannerPlanting(models.Model):
    area = models.ForeignKey(
        PlannerArea,
        on_delete=models.CASCADE,
        related_name="plantings",
        verbose_name="Зона",
    )
    plant = models.OneToOneField(
        "Plant",
        on_delete=models.CASCADE,
        related_name="planner_placement",
        verbose_name="Рослина або посадка",
    )
    mode = models.CharField(
        max_length=24,
        choices=PLANNER_PLANTING_MODE_CHOICES,
        default="unknown",
        verbose_name="Спосіб розміщення",
    )
    status = models.CharField(
        max_length=16,
        choices=PLANNER_PLANTING_STATUS_CHOICES,
        default="planned",
        verbose_name="Статус",
    )
    quantity = models.PositiveIntegerField(null=True, blank=True, verbose_name="Кількість")
    rows = models.PositiveIntegerField(null=True, blank=True, verbose_name="Кількість рядів")
    occupied_area_m2 = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
        verbose_name="Зайнята площа, м²",
    )
    notes = models.CharField(max_length=255, blank=True, verbose_name="Примітка")
    x_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default="5.00",
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        verbose_name="X, %",
    )
    y_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default="5.00",
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
        verbose_name="Y, %",
    )
    width_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default="35.00",
        validators=[MinValueValidator(Decimal("5")), MaxValueValidator(Decimal("100"))],
        verbose_name="Ширина, %",
    )
    height_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default="35.00",
        validators=[MinValueValidator(Decimal("5")), MaxValueValidator(Decimal("100"))],
        verbose_name="Висота, %",
    )
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created", "id")

    def __str__(self):
        return f"{self.plant.display_name} — {self.get_mode_display()}"

    @property
    def layout_summary(self):
        if self.mode == "exact" and self.quantity:
            return f"{self.quantity} шт."
        if self.mode == "approximate" and self.quantity:
            return f"≈ {self.quantity} шт."
        if self.mode == "rows" and self.rows:
            rows_label = "ряд" if self.rows % 10 == 1 and self.rows % 100 != 11 else "ряди"
            if self.rows % 10 not in {1, 2, 3, 4} or self.rows % 100 in {11, 12, 13, 14}:
                rows_label = "рядів"
            return f"{self.rows} {rows_label}"
        if self.mode == "area" and self.occupied_area_m2 is not None:
            amount = format(self.occupied_area_m2.normalize(), "f").rstrip("0").rstrip(".")
            return f"{amount} м²"
        if self.mode == "broadcast":
            return "суцільний посів"
        return "без підрахунку"


class PlannerTask(models.Model):
    planner = models.ForeignKey(
        Planner,
        on_delete=models.CASCADE,
        related_name="tasks",
        verbose_name="Планер",
    )
    area = models.ForeignKey(
        PlannerArea,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks",
        verbose_name="Зона",
    )
    title = models.CharField(max_length=255, verbose_name="Завдання")
    due_date = models.DateField(null=True, blank=True, verbose_name="Запланована дата")
    is_completed = models.BooleanField(default=False, verbose_name="Виконано")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Виконано о")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("is_completed", "due_date", "created", "id")

    def __str__(self):
        return self.title


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
    harvest_amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Кількість урожаю",
    )
    harvest_unit = models.CharField(
        max_length=16,
        choices=HARVEST_UNIT_CHOICES,
        blank=True,
        default="",
        verbose_name="Одиниця урожаю",
    )
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

    @property
    def harvest_summary(self):
        if self.action_type != "harvest" or self.harvest_amount is None or not self.harvest_unit:
            return ""
        amount = self.harvest_amount.normalize()
        amount_text = format(amount, "f").rstrip("0").rstrip(".")
        return f"{amount_text} {self.get_harvest_unit_display()}"

    @property
    def action_icon(self):
        label = self.get_action_type_display()
        return label.split(" ", 1)[0] if label else "✏️"

    @property
    def action_label(self):
        label = self.get_action_type_display()
        return label.split(" ", 1)[1] if " " in label else label
