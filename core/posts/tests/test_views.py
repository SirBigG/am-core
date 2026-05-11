from django.test import Client, RequestFactory, TestCase

from core.utils.tests.factories import CategoryFactory, PhotoFactory, PostFactory

client = Client()

request = RequestFactory()


class MainPageTest(TestCase):

    def test_response(self):
        parent = CategoryFactory()
        rubric = CategoryFactory(parent=parent)
        PostFactory.create_batch(3, rubric=rubric)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("object_list", response.context)
        self.assertTemplateUsed(response, "index.html")

    def test_active_status_filter(self):
        parent = CategoryFactory()
        rubric = CategoryFactory(parent=parent)
        PostFactory.create_batch(2, rubric=rubric)
        PostFactory.create_batch(2, status=0, rubric=rubric)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["object_list"].count(), 2)

    def test_service_worker_served_from_current_origin(self):
        response = self.client.get("/service-worker.js")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "application/javascript")
        self.assertEqual(response.headers["Cache-Control"], "no-cache")


class PostListTests(TestCase):

    def setUp(self):
        self.parent = CategoryFactory()
        self.category = CategoryFactory(parent=self.parent)
        self.post = PostFactory(rubric=self.category)

    def test_parent_list(self):
        response = client.get("/%s/" % self.parent.slug)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "posts/parent_index.html")
        self.assertEqual(response.context["category"], self.parent)
        self.assertEqual(len(response.context["object_list"]), 1)

    def test_parent_list_404(self):
        response = client.get("/unknown/")
        self.assertEqual(response.status_code, 404)

    def test_child_list_grouped(self):
        slug = self.post.rubric.slug
        response = client.get(f"/{self.parent.slug}/{slug}/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "posts/list_order.html")

    def test_child_list(self):
        slug = self.post.rubric.slug
        response = client.get(f"/{self.parent.slug}/{slug}/list/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "posts/list.html")
        self.assertEqual(len(response.context["object_list"]), 1)
        PostFactory(rubric=self.post.rubric)
        PostFactory(rubric=self.post.rubric)
        response = client.get(f"/{self.parent.slug}/{slug}/list/")
        self.assertEqual(len(response.context["object_list"]), 3)
        self.assertEqual(response.context["category"], self.post.rubric)

    def test_child_list_404(self):
        response = client.get("/%s/unknown/" % self.parent.slug)
        self.assertEqual(response.status_code, 404)


class PostDetailTests(TestCase):

    def setUp(self):
        self.parent = CategoryFactory()
        child = CategoryFactory(parent=self.parent)
        self.category = CategoryFactory(parent=child)
        self.post = PostFactory(rubric=self.category)

    def test_detail(self):
        response = client.get(self.post.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "posts/detail.html")
        self.assertIn("object", response.context)
        self.assertEqual(len(response.context["menu_items"]), 1)

    def test_detail_does_not_show_add_photo_link(self):
        PhotoFactory(post=self.post)
        response = client.get(self.post.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "/gallery/add/")
        self.assertNotContains(response, "Додати фото до публікації")


class GalleryTests(TestCase):

    def setUp(self):
        self.parent = CategoryFactory()
        self.category = CategoryFactory(parent=self.parent)
        self.post = PostFactory(rubric=self.category)

    def test_gallery_does_not_show_add_photo_link(self):
        PhotoFactory(post=self.post)
        response = client.get("/gallery/%s/" % self.post.id)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "/gallery/add/")
        self.assertNotContains(response, "Завантажити фото публікації")

    def test_gallery_add_photo_url_is_not_available(self):
        response = client.get("/gallery/add/%s/" % self.post.id)
        self.assertEqual(response.status_code, 404)


class SiteMapTests(TestCase):
    def setUp(self):
        root = CategoryFactory()
        parent = CategoryFactory(parent=root)
        child = CategoryFactory(parent=parent)
        PostFactory.create_batch(5, **{"rubric": child})

    def test_return_context(self):
        response = client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["urls"]), 3)
        self.assertTemplateUsed(response, "sitemap_index.xml")


class ErrorsHandlerTests(TestCase):

    def test_404_handler_using(self):
        response = client.get("/sdg/sdg/dfdg")
        self.assertTemplateUsed(response, "404.html")
        self.assertTemplateUsed(response, "header.html")
        self.assertTemplateUsed(response, "footer.html")

    # TODO: create test for 500 handler
