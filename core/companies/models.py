import re
import uuid
from collections import Counter
from datetime import timedelta
from string import punctuation

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import get_language
from transliterate import slugify

from core.classifier.models import Location
from core.posts.models import Post

DEFAULT_PARSER_CRAWL_INTERVAL_MINUTES = 24 * 60


def get_minimum_parser_crawl_interval_minutes():
    return max(0, int(getattr(settings, "PARSER_MIN_CRAWL_INTERVAL_MINUTES", DEFAULT_PARSER_CRAWL_INTERVAL_MINUTES)))


def get_parser_failure_retry_minutes():
    return max(0, int(getattr(settings, "PARSER_FAILURE_RETRY_MINUTES", 60)))


def normalize_product_post_match_text(value):
    value = (value or "").casefold()
    translation_table = str.maketrans({character: " " for character in punctuation + "«»“”„’ʼ`´"})
    return " ".join(value.translate(translation_table).split())


def assess_product_post(product):
    """Rank cultivar names in seller titles; never use article body
    relevance."""
    name = normalize_product_post_match_text(product.name)
    if not name or not product.category_id:
        return None, "Немає назви або категорії."
    candidates = list(Post.objects.filter(rubric_id=product.category_id, status=True).only("id", "title"))
    exact = [post for post in candidates if normalize_product_post_match_text(post.title) == name]
    if len(exact) == 1:
        return exact[0], "Єдиний повний збіг нормалізованої назви в категорії."
    if len(exact) > 1:
        return None, "Декілька публікацій з однаковою назвою: потрібна перевірка."
    rules = list(ProductMatchRule.objects.filter(active=True).values_list("word", "purpose", "prefix"))
    name_tokens = set(name.split())
    bundle = any(
        any(token.startswith(word) if prefix else token == word for token in name_tokens)
        for word, purpose, prefix in rules
        if purpose == ProductMatchRule.Purpose.BUNDLE
    )
    ignored = {word for word, purpose, prefix in rules if purpose == ProductMatchRule.Purpose.IGNORE}
    if "+" in (product.name or "") or bundle:
        return None, "Комплект або кілька сортів: одна прив’язка не описує товар."

    def tokens(text):
        return set(normalize_product_post_match_text(text).split()) - ignored

    # Parenthetical/pipe-separated names are explicit catalog aliases, not
    # machine-invented synonyms. Score at post level so aliases do not tie.
    aliases = {post.pk: [part for part in re.split(r"[|()]", post.title) if tokens(part)] for post in candidates}
    frequency = Counter(token for post in candidates for token in set().union(*(tokens(a) for a in aliases[post.pk])))
    product_tokens = tokens(name)
    ranked = []
    for post in candidates:
        best = 0
        for alias in aliases[post.pk]:
            normalized = normalize_product_post_match_text(alias)
            title_tokens = tokens(alias)
            if not title_tokens:
                continue
            if f" {normalized} " in f" {name} ":
                # Prefer a specific multiword cultivar over a contained base name.
                score = 90 + min(len(title_tokens), 8)
            else:
                shared = title_tokens & product_tokens
                coverage = len(shared) / len(title_tokens)
                distinctive = {t for t in shared if len(t) >= 4 and frequency[t] == 1}
                score = 70 + int(20 * coverage) if distinctive and coverage >= 0.5 else 0
            best = max(best, score)
        if best:
            ranked.append((best, post))
    ranked.sort(key=lambda pair: (-pair[0], pair[1].pk))
    if not ranked:
        return None, "Надійного збігу немає. Сорт може бути відсутній у каталозі."
    score, post = ranked[0]
    if len(ranked) > 1 and ranked[1][0] == score:
        return None, ("Рівнозначні кандидати: " + "; ".join(p.title for value, p in ranked if value == score))[:1000]
    return post, ("Автоматично за назвою в заголовку; перевірте сорт/варіант: " + post.title)[:1000]


def match_product_post(product):
    return assess_product_post(product)[0]


class ProductMatchRule(models.Model):
    class Purpose(models.TextChoices):
        IGNORE = "ignore", "Ігнорувати при зіставленні"
        BUNDLE = "bundle", "Маркер комплекту / кількох сортів"

    word = models.CharField(
        "Слово",
        max_length=100,
        unique=True,
        help_text="Одне слово, без пробілів і пунктуації. Регістр не має значення.",
    )
    purpose = models.CharField("Призначення", max_length=16, choices=Purpose.choices, default=Purpose.IGNORE)
    prefix = models.BooleanField(
        "Збіг за початком слова", default=False, help_text="Лише для маркерів комплектів: охоплює закінчення слова."
    )
    active = models.BooleanField("Активне", default=True)

    class Meta:
        ordering = ("purpose", "word")
        verbose_name = "Правило зіставлення товарів"
        verbose_name_plural = "Словник зіставлення товарів"

    def clean(self):
        super().clean()
        self.word = normalize_product_post_match_text(self.word)
        if len(self.word.split()) != 1:
            raise ValidationError({"word": "Вкажіть одне непорожнє слово."})
        if self.prefix and self.purpose != self.Purpose.BUNDLE:
            raise ValidationError({"prefix": "Збіг за початком доступний лише для маркерів комплектів."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.word


class CompanyType(models.IntegerChoices):
    SHOP = 1, "Магазин"
    SERVICE = 2, "Сервіс"
    SUPERMARKET = 3, "Супермаркет"
    MARKET = 4, "Ринок"


class Company(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, blank=True, null=True, unique=True)
    type = models.PositiveSmallIntegerField(choices=CompanyType, default=CompanyType.SHOP)
    description = models.TextField(blank=True, null=True)
    logo = models.ImageField(upload_to="companies", blank=True, null=True)
    active = models.BooleanField(default=True)
    website = models.URLField()
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    parser_map = models.JSONField(blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Company"
        verbose_name_plural = "Companies"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name.lower(), get_language())
        super().save(*args, **kwargs)

    def get_slug(self):
        return self.slug or slugify(self.name.lower(), get_language())

    def get_absolute_url(self):
        return reverse("companies:detail", args=[self.get_slug(), str(self.id)])


class CurrencyChoices(models.TextChoices):
    UAH = "UAH", "грн."
    USD = "USD", "$"
    EUR = "EUR", "€"
    GBP = "GBP", "£"


class Product(models.Model):
    class MatchStatus(models.TextChoices):
        REVIEW = "review", "Потребує перевірки"
        AUTO = "auto", "Повний збіг назви"
        CONFIRMED = "confirmed", "Підтверджено адміністратором"

    match_status = models.CharField(
        max_length=16, choices=MatchStatus.choices, default=MatchStatus.REVIEW, db_index=True
    )
    match_reason = models.CharField(max_length=1000, blank=True, default="Попередній запис: зіставлення не перевірене.")

    name = models.CharField(max_length=200, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    company = models.ForeignKey(Company, related_name="products", on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.SET_NULL, blank=True, null=True)
    category = models.ForeignKey("classifier.Category", on_delete=models.SET_NULL, blank=True, null=True)
    link = models.URLField(blank=True, null=True)
    source_link = models.ForeignKey("Link", related_name="products", on_delete=models.SET_NULL, blank=True, null=True)
    source_product_key = models.CharField(max_length=500, blank=True, null=True, db_index=True)
    active = models.BooleanField(default=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    max_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    min_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    price_updated_at = models.DateTimeField(blank=True, null=True)
    last_seen_at = models.DateTimeField(blank=True, null=True, db_index=True)
    consecutive_missing_count = models.PositiveIntegerField(default=0)
    currency = models.CharField(choices=CurrencyChoices, default=CurrencyChoices.UAH, blank=True, null=True)
    auction_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    auction_currency = models.CharField(choices=CurrencyChoices, default=CurrencyChoices.UAH, blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name or self.description

    def has_fresh_price(self):
        if not self.price or not self.price_updated_at:
            return False
        fresh_after = timezone.now() - timedelta(days=settings.PRODUCT_PRICE_FRESH_DAYS)
        return self.price_updated_at >= fresh_after

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        if update_fields is not None and not update_fields:
            return
        update_fields = self._refresh_price_timestamp(update_fields)
        original = None
        if self.pk:
            original = (
                type(self).objects.filter(pk=self.pk).values("name", "category_id", "post_id", "match_status").first()
            )
        fields = None if update_fields is None else set(update_fields)
        identity_changed = bool(
            original
            and any(
                (fields is None or field in fields or f"{field}_id" in fields)
                and getattr(self, f"{field}_id" if field == "category" else field)
                != original[f"{field}_id" if field == "category" else field]
                for field in ("name", "category")
            )
        )
        post_changed = bool(
            original
            and (fields is None or "post" in fields or "post_id" in fields)
            and self.post_id != original["post_id"]
        )
        if post_changed:
            self.match_status = self.MatchStatus.CONFIRMED
            self.match_reason = "Ручне рішення щодо прив’язки."
        elif self.match_status != self.MatchStatus.CONFIRMED:
            if identity_changed and (
                original["match_status"] == self.MatchStatus.AUTO
                or self.match_reason.startswith("Автоматично за назвою")
            ):
                self.post = None
            if not self.post_id and (original is None or identity_changed or fields is None):
                self.post, self.match_reason = assess_product_post(self)
                self.match_status = (
                    self.MatchStatus.AUTO
                    if self.post_id
                    and normalize_product_post_match_text(self.name)
                    == normalize_product_post_match_text(self.post.title)
                    else self.MatchStatus.REVIEW
                )
        if fields is not None:
            fields.update({"post", "match_status", "match_reason"})
            update_fields = fields
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def _refresh_price_timestamp(self, update_fields):
        if self.price is None and self.min_price is None and self.max_price is None:
            return update_fields

        original = None
        if self.pk:
            original = (
                type(self)
                .objects.filter(pk=self.pk)
                .values("price", "min_price", "max_price", "currency", "price_updated_at")
                .first()
            )

        if not original:
            if not self.price_updated_at:
                self.price_updated_at = timezone.now()
                if update_fields is not None and any(
                    field in update_fields for field in ("price", "min_price", "max_price", "currency")
                ):
                    update_fields = set(update_fields)
                    update_fields.add("price_updated_at")
            return update_fields

        price_changed = any(
            getattr(self, field) != original[field] for field in ("price", "min_price", "max_price", "currency")
        )
        timestamp_was_explicitly_changed = original and self.price_updated_at != original["price_updated_at"]
        should_refresh = not self.price_updated_at or (price_changed and not timestamp_was_explicitly_changed)
        if not should_refresh:
            return update_fields

        self.price_updated_at = timezone.now()
        if update_fields is not None and any(
            field in update_fields for field in ("price", "min_price", "max_price", "currency")
        ):
            update_fields = set(update_fields)
            update_fields.add("price_updated_at")
        return update_fields

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source_link", "source_product_key"],
                condition=Q(source_link__isnull=False, source_product_key__isnull=False),
                name="companies_product_unique_source_product",
            ),
        ]


class Link(models.Model):
    SOURCE_TYPE_STATIC = "static"
    SOURCE_TYPE_BROWSER = "browser"
    SOURCE_TYPE_CHOICES = [
        (SOURCE_TYPE_STATIC, "Static HTML"),
        (SOURCE_TYPE_BROWSER, "Browser-rendered page"),
    ]

    url = models.URLField()
    company = models.ForeignKey(Company, related_name="links", on_delete=models.CASCADE)
    category = models.ForeignKey("classifier.Category", related_name="links", on_delete=models.CASCADE)
    parser_map = models.JSONField(blank=True, null=True)
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPE_CHOICES, default=SOURCE_TYPE_STATIC)
    experiment_label = models.CharField(max_length=100, blank=True, db_index=True)
    parser_config_version = models.CharField(max_length=64, blank=True)
    priority = models.PositiveIntegerField(default=100, db_index=True)
    crawl_interval_minutes = models.PositiveIntegerField(default=DEFAULT_PARSER_CRAWL_INTERVAL_MINUTES)
    active = models.BooleanField(default=True)
    last_crawled = models.DateTimeField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)
    last_crawl_status = models.PositiveIntegerField(blank=True, null=True)
    leased_by = models.CharField(max_length=100, blank=True, null=True)
    lease_token = models.UUIDField(blank=True, null=True)
    leased_until = models.DateTimeField(blank=True, null=True, db_index=True)
    last_success_at = models.DateTimeField(blank=True, null=True)
    last_error_at = models.DateTimeField(blank=True, null=True)
    last_error = models.TextField(blank=True)
    last_product_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.url

    def is_lease_active(self):
        return bool(self.lease_token and self.leased_until and self.leased_until > timezone.now())

    def is_due(self, now=None):
        now = now or timezone.now()
        if self.last_error_at and self.last_error_at > now - timedelta(minutes=get_parser_failure_retry_minutes()):
            return False
        if not self.last_crawled:
            return True
        return self.last_crawled <= now - timedelta(minutes=self.effective_crawl_interval_minutes())

    def effective_crawl_interval_minutes(self):
        return max(self.crawl_interval_minutes, get_minimum_parser_crawl_interval_minutes())

    def lease(self, worker_name, duration_minutes=30):
        self.leased_by = worker_name[:100]
        self.lease_token = uuid.uuid4()
        self.leased_until = timezone.now() + timedelta(minutes=duration_minutes)
        self.save(update_fields=["leased_by", "lease_token", "leased_until"])
        return self.lease_token

    def has_valid_lease(self, lease_token, worker_name=None):
        try:
            lease_uuid = uuid.UUID(str(lease_token))
        except (TypeError, ValueError, AttributeError) as error:
            del error
            return False
        if self.lease_token != lease_uuid or not self.leased_until or self.leased_until <= timezone.now():
            return False
        if worker_name and self.leased_by != worker_name:
            return False
        return True

    def save_result_products(self, data):
        for obj in data:
            name = obj.pop("name", None)
            Product.objects.update_or_create(
                defaults=obj, **{"company_id": self.company_id, "category_id": self.category_id, "name": name}
            )

    class Meta:
        permissions = [
            ("use_parser_worker_api", "Can use parser worker API"),
            ("run_parser_source_on_demand", "Can run parser sources on demand"),
        ]


class ParserSourceAttempt(models.Model):
    STATUS_SUCCESS = "success"
    STATUS_FAILURE = "failure"
    STATUS_CHOICES = [
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILURE, "Failure"),
    ]

    source_link = models.ForeignKey(Link, related_name="parser_attempts", on_delete=models.CASCADE)
    worker_name = models.CharField(max_length=100, blank=True)
    lease_token = models.UUIDField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    crawl_status = models.PositiveIntegerField(blank=True, null=True)
    product_count = models.PositiveIntegerField(default=0)
    error = models.TextField(blank=True)
    snapshot_complete = models.BooleanField(default=False)
    parser_config_version = models.CharField(max_length=64, blank=True)
    parser_config = models.JSONField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Parser source attempt"
        verbose_name_plural = "Parser source attempts"
        ordering = ["-created"]

    def __str__(self):
        return f"{self.source_link} {self.status} {self.created}"


class ProductPriceHistory(models.Model):
    product = models.ForeignKey(Product, related_name="price_history", on_delete=models.CASCADE)
    source_link = models.ForeignKey(
        Link, related_name="price_history", on_delete=models.SET_NULL, blank=True, null=True
    )
    price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    max_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    min_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    currency = models.CharField(choices=CurrencyChoices, default=CurrencyChoices.UAH, blank=True, null=True)
    observed_at = models.DateTimeField()
    raw_price = models.CharField(max_length=255, blank=True)
    raw_data = models.JSONField(blank=True, null=True)
    worker_name = models.CharField(max_length=100, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Product price history"
        verbose_name_plural = "Product price history"
        ordering = ["-observed_at", "-created"]
        indexes = [
            models.Index(fields=["product", "-observed_at"], name="companies_price_product_obs"),
            models.Index(fields=["source_link", "-observed_at"], name="companies_price_source_obs"),
        ]

    def __str__(self):
        return f"{self.product} {self.price} {self.currency} {self.observed_at}"
