import factory
from django.contrib.auth.hashers import make_password
from django.utils import timezone

from core.classifier.models import Area, Category, Country, Location, Region
from core.events.models import Event, EventType
from core.posts.models import CategoryAttributeChoice, CategoryAttributeField, CategoryAttributeGroup, Photo, Post
from core.pro_auth.models import User
from core.services.models import Feedback, MetaData, Reviews


class BaseFactory(factory.django.DjangoModelFactory):
    """Base factory for all project factories.

    You need inherit it in your factory.
    """

    pass


# ###############   Classifier factories     #################### #


class CountryFactory(BaseFactory):
    """Creating country."""

    class Meta:
        model = Country

    slug = "ukraine"
    short_slug = "uk"
    value = factory.Sequence(lambda n: f"Україна{n}")


class RegionFactory(BaseFactory):
    """Creating region."""

    class Meta:
        model = Region

    slug = "kiev_region"
    value = factory.Sequence(lambda n: f"Київська область{n}")
    country = factory.SubFactory(CountryFactory)


class AreaFactory(BaseFactory):
    """Creating area."""

    class Meta:
        model = Area

    slug = "kiev_area"
    value = factory.Sequence(lambda n: f"Київський район{n}")
    region = factory.SubFactory(RegionFactory)


class LocationFactory(BaseFactory):
    """Creating locations."""

    class Meta:
        model = Location

    slug = "kiev"
    value = "Київ"
    country = factory.SubFactory(CountryFactory)
    region = factory.SubFactory(RegionFactory)
    area = factory.SubFactory(AreaFactory)


class CategoryFactory(BaseFactory):
    """Creating post categories."""

    class Meta:
        model = Category

    slug = factory.sequence(lambda n: f"category{n}")
    value = "Категорія"


# ##################   User factories     ####################### #


class UserFactory(BaseFactory):
    """Custom user modal factory."""

    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"agrokent{n}@test.com")
    first_name = "John"
    last_name = "Dou"
    password = make_password("12345")
    is_active = True
    is_staff = False
    phone1 = "+380991234567"
    location = factory.SubFactory(LocationFactory)


class StaffUserFactory(UserFactory):
    """Creating users with staff privileges."""

    is_staff = True


# ##################   Post factories     ####################### #


class PostFactory(BaseFactory):
    """Creation posts."""

    class Meta:
        model = Post

    title = "Заголовок"
    text = "Текст"
    slug = factory.Sequence(lambda n: f"post{n}")
    publisher = factory.SubFactory(UserFactory)
    rubric = factory.SubFactory(CategoryFactory)


class PhotoFactory(BaseFactory):
    """Creation photos for posts."""

    class Meta:
        model = Photo

    image = factory.django.ImageField(color="green", width=1500, height=1000)
    post = factory.SubFactory(PostFactory)


class CategoryAttributeGroupFactory(BaseFactory):
    class Meta:
        model = CategoryAttributeGroup

    category = factory.SubFactory(CategoryFactory)
    title = factory.Sequence(lambda n: f"Attribute group {n}")
    sort_order = factory.Sequence(lambda n: n)


class CategoryAttributeFieldFactory(BaseFactory):
    class Meta:
        model = CategoryAttributeField

    category = factory.SubFactory(CategoryFactory)
    group = factory.SubFactory(CategoryAttributeGroupFactory, category=factory.SelfAttribute("..category"))
    key = factory.Sequence(lambda n: f"attribute_{n}")
    label = factory.Sequence(lambda n: f"Attribute {n}")
    field_type = "select"
    sort_order = factory.Sequence(lambda n: n)


class CategoryAttributeChoiceFactory(BaseFactory):
    class Meta:
        model = CategoryAttributeChoice

    field = factory.SubFactory(CategoryAttributeFieldFactory)
    value = factory.Sequence(lambda n: f"choice_{n}")
    label = factory.Sequence(lambda n: f"Choice {n}")
    sort_order = factory.Sequence(lambda n: n)


# ##################   Services factories     ####################### #


class FeedbackFactory(BaseFactory):
    """Creation feedbacks."""

    class Meta:
        model = Feedback

    title = "Feedback topic"
    email = "test@test.com"
    text = "Feedback text"


class MetaDataFactory(BaseFactory):
    class Meta:
        model = MetaData

    title = "title"
    description = "description"
    h1 = "h1"


class ReviewsFactory(BaseFactory):
    class Meta:
        model = Reviews

    description = "description"
    mark = 5


class EventTypeFactory(BaseFactory):
    class Meta:
        model = EventType

    title = "event type title"
    slug = factory.Sequence(lambda n: f"event-type-{n}")


class EventFactory(BaseFactory):
    class Meta:
        model = Event

    user = factory.SubFactory(UserFactory)
    title = "title"
    slug = factory.Sequence(lambda n: f"event{n}")
    text = "text"
    start = timezone.now()
    stop = timezone.now() + timezone.timedelta(days=1)
    type = factory.SubFactory(EventTypeFactory)
    location = factory.SubFactory(LocationFactory)
    poster = factory.django.ImageField(color="green", width=300, height=200)
