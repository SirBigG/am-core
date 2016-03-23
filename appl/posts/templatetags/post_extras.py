# -*- coding: utf-8 -*-

from django import template

from appl.posts.models import Post
from appl.classifier.models import Category


register = template.Library()


@register.inclusion_tag('posts/main_list.html')
def posts_list(number):
    """
    Creating list of last posts for index page.
    :param number: int
    :return: posts queryset
    """
    qs = Post.objects.all().order_by('-publish_date')[:number]
    return {'posts': qs}


@register.inclusion_tag('posts/main_menu.html')
def main_menu():
    """
    Creating main page menu.
    :return: rubric roots queryset
    """
    roots = Category.objects.filter(level=0)
    return {'roots': roots}
