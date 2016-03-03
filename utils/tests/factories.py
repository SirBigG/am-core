# -*- coding: utf-8 -*-

import factory

from appl.pro_auth.models import User
from appl.classifier.models import Location, Country, Region, \
    Area


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


class AreaFactory(BaseFactory):
    """
    Creating area.
    """
    class Meta:
        model = Area

    slug = 'kiev_area'
    value = factory.Sequence(lambda n: u'Київський район{0}'.format(n))


class LocationFactory(BaseFactory):
    """
    Creating locations.
    """
    class Meta:
        model = Location

    slug = 'kiev'
    value = u'Київ'
    country = factory.SubFactory(CountryFactory)
    region = factory.SubFactory(RegionFactory)
    area = factory.SubFactory(AreaFactory)


# ##################   User factories     ####################### #


class UserFactory(BaseFactory):
    """
    Custom user modal factory.
    """
    class Meta:
        model = User

    email = factory.Sequence(lambda n: 'agrokent{0}@test.com'.format(n))
    first_name = 'John'
    last_name = 'Dou'
    password = '12345'
    is_active = True
    is_staff = False
    phone1 = '+380991234567'
    location = factory.SubFactory(LocationFactory)


class StaffUserFactory(UserFactory):
    """
    Creating users with staff privileges.
    """
    is_staff = True
