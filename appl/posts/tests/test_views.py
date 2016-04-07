# -*- coding: utf-8 -*-

from django.test import TestCase, Client

from utils.tests.factories import PostFactory, CategoryFactory


client = Client()


class PostListTests(TestCase):

    def setUp(self):
        self.parent = CategoryFactory()
        self.category = CategoryFactory(parent=self.parent)
        self.post = PostFactory(rubric=self.category)

    def test_parent_list(self):
        response = client.get('/' + self.parent.slug + '/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['object_list']), 1)
        PostFactory(rubric=self.post.rubric)
        PostFactory(rubric=self.post.rubric)
        response = client.get('/' + self.parent.slug + '/')
        self.assertEqual(len(response.context['object_list']), 3)

    def test_child_list(self):
        slug = self.post.rubric.slug
        response = client.get('/' + self.parent.slug + '/' + slug + '/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'posts/list.html')
        self.assertEqual(len(response.context['object_list']), 1)
        PostFactory(rubric=self.post.rubric)
        PostFactory(rubric=self.post.rubric)
        response = client.get('/' + self.parent.slug + '/' + slug + '/')
        self.assertEqual(len(response.context['object_list']), 3)
        self.assertEqual(len(response.context['menu_items']), 1)


class PostDetailTests(TestCase):

    def setUp(self):
        self.parent = CategoryFactory()
        child = CategoryFactory(parent=self.parent)
        self.category = CategoryFactory(parent=child)
        self.post = PostFactory(rubric=self.category)

    def test_detail(self):
        response = client.get(self.post.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'posts/detail.html')
        self.assertIn('object', response.context)
