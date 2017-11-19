import factory

from core.pro_auth.models import User
from core.classifier.models import Location, Country, Region, \
    Area, Category
from core.posts.models import Post, Photo, Comment
from core.services.models import Feedback, MetaData, Comments, Reviews
from core.events.models import Event, EventType

from django.contrib.auth.hashers import make_password
from django.utils import timezone


class BaseFactory(factory.django.DjangoModelFactory):
    """
    Base factory for all project factories.
    You need inherit it in your factory.
    """
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        obj = model_class(*args, **kwargs)
        obj.save()
        return obj


# ###############   Classifier factories     #################### #


class CountryFactory(BaseFactory):
    """
    Creating country.
    """
    class Meta:
        model = Country

    slug = 'ukraine'
    short_slug = 'uk'
    value = factory.Sequence(lambda n: u'Україна{0}'.format(n))


class RegionFactory(BaseFactory):
    """
    Creating region.
    """
    class Meta:
        model = Region

    slug = 'kiev_region'
    value = factory.Sequence(lambda n: u'Київська область{0}'.format(n))
    country = factory.SubFactory(CountryFactory)


class AreaFactory(BaseFactory):
    """Creating area."""
    class Meta:
        model = Area

    slug = 'kiev_area'
    value = factory.Sequence(lambda n: u'Київський район{0}'.format(n))
    region = factory.SubFactory(RegionFactory)


class LocationFactory(BaseFactory):
    """Creating locations."""
    class Meta:
        model = Location

    slug = 'kiev'
    value = u'Київ'
    country = factory.SubFactory(CountryFactory)
    region = factory.SubFactory(RegionFactory)
    area = factory.SubFactory(AreaFactory)


class CategoryFactory(BaseFactory):
    """Creating post categories."""
    class Meta:
        model = Category

    slug = factory.sequence(lambda n: 'category{0}'.format(n))
    value = u'Категорія'


# ##################   User factories     ####################### #


class UserFactory(BaseFactory):
    """Custom user modal factory."""
    class Meta:
        model = User

    email = factory.Sequence(lambda n: 'agrokent{0}@test.com'.format(n))
    first_name = 'John'
    last_name = 'Dou'
    password = make_password('12345')
    is_active = True
    is_staff = False
    phone1 = '+380991234567'
    location = factory.SubFactory(LocationFactory)


class StaffUserFactory(UserFactory):
    """Creating users with staff privileges."""
    is_staff = True


# ##################   Post factories     ####################### #


class PostFactory(BaseFactory):
    """Creation posts."""
    class Meta:
        model = Post

    title = u'Заголовок'
    text = u'Текст'
    slug = factory.Sequence(lambda n: 'post{0}'.format(n))
    publisher = factory.SubFactory(UserFactory)
    rubric = factory.SubFactory(CategoryFactory)


class PhotoFactory(BaseFactory):
    """Creation photos for posts."""
    class Meta:
        model = Photo

    image = factory.django.ImageField(color='green', width=1500, height=1000)
    post = factory.SubFactory(PostFactory)


class CommentFactory(BaseFactory):
    """Creation comments for posts."""
    class Meta:
        model = Comment

    post = factory.SubFactory(PostFactory)
    text = u'Коментарій'
    user = factory.SubFactory(UserFactory)


# ##################   Services factories     ####################### #


class FeedbackFactory(BaseFactory):
    """Creation feedbacks."""
    class Meta:
        model = Feedback

    title = 'Feedback topic'
    email = 'test@test.com'
    text = 'Feedback text'


class MetaDataFactory(BaseFactory):
    class Meta:
        model = MetaData

    title = 'title'
    description = 'description'
    h1 = 'h1'


class CommentsFactory(BaseFactory):
    class Meta:
        model = Comments

    text = 'comment text'


class ReviewsFactory(BaseFactory):
    class Meta:
        model = Reviews

    description = 'description'
    mark = 5


class EventTypeFactory(BaseFactory):
    class Meta:
        model = EventType

    title = "event type title"
    slug = factory.Sequence(lambda n: 'event-type-{0}'.format(n))


class EventFactory(BaseFactory):
    class Meta:
        model = Event

    title = 'title'
    slug = factory.Sequence(lambda n: 'event{0}'.format(n))
    text = 'text'
    start = timezone.now()
    stop = timezone.now() + timezone.timedelta(days=1)
    type = factory.SubFactory(EventTypeFactory)
    location = factory.SubFactory(LocationFactory)
