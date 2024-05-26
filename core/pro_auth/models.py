from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.mail import send_mail
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        """Creates and saves a User with the given email and password."""
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Model for all project users.

    Email, phone1 and password are required. Other fields are optional.
    """

    email = models.EmailField(
        blank=True,
        null=True,
        help_text=_("Required. You use it at every entrance to the site."),
        error_messages={
            "unique": _("A user with that email already exists."),
        },
        verbose_name=_("user email"),
    )
    # Social auth extra data field
    details = models.TextField(blank=True, null=True)

    first_name = models.CharField(_("first name"), max_length=30, blank=True)
    last_name = models.CharField(_("last name"), max_length=30, blank=True)

    phone1 = models.CharField(max_length=25, blank=True, null=True, verbose_name=_("main phone"))
    phone2 = models.CharField(max_length=25, blank=True, null=True, verbose_name=_("extra phone"))
    phone3 = models.CharField(max_length=25, blank=True, null=True, verbose_name=_("extra phone"))

    location = models.ForeignKey(
        "classifier.Location", blank=True, null=True, on_delete=models.CASCADE, verbose_name=_("user location")
    )
    birth_date = models.DateField(blank=True, null=True, verbose_name=_("date of birth"))

    validation_key = models.CharField(max_length=255, blank=True, null=True, verbose_name=_("mail validation key"))

    choices_owner = models.ManyToManyField(
        "posts.Post", blank=True, related_name="user_post", verbose_name=_("relation with posts")
    )

    is_staff = models.BooleanField(
        _("staff status"),
        default=False,
        help_text=_("Designates whether the user can log into this admin site."),
    )
    is_active = models.BooleanField(
        _("active"),
        default=True,
        help_text=_(
            "Designates whether this user should be treated as active. " "Unselect this instead of deleting accounts."
        ),
    )
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)

    avatar = models.ImageField(upload_to="avatars", blank=True, verbose_name=_("avatar"))

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["phone1"]

    class Meta:
        db_table = "custom_user"
        verbose_name = _("custom user")
        verbose_name_plural = _("custom users")
        swappable = "AUTH_USER_MODEL"

    def __str__(self):
        if self.first_name:
            return f"{self.first_name} {self.last_name}"
        return self.email

    def get_full_name(self):
        """Returns the first_name plus the last_name, with a space in
        between."""
        return f"{self.first_name} {self.last_name}".strip() or self.email

    def get_short_name(self):
        """Returns the short name for the user."""
        return self.first_name

    def email_user(self, subject, message, from_email=None, **kwargs):
        """Sends an email to this User."""
        send_mail(subject, message, from_email, [self.email], **kwargs)

    @property
    def username(self):
        return self.get_full_name()


backend = settings.AUTHENTICATION_BACKENDS
