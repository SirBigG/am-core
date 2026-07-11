from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from core.classifier.models import Category
from core.posts.models import Post
from core.utils.tests.factories import CategoryFactory, CountryFactory, PhotoFactory, PostFactory, UserFactory


class ContentApiTestCase(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.token = Token.objects.create(user=self.user)

    def authenticate(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")


class ContentAuthenticationTests(ContentApiTestCase):
    def test_endpoints_require_token(self):
        for url in ("/api/content/categories/tree/", "/api/content/countries/", "/api/content/posts/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 401)


class CategoryTreeTests(ContentApiTestCase):
    def test_returns_complete_active_tree(self):
        root = CategoryFactory(value="Root")
        child = CategoryFactory(parent=root, value="Child")
        grandchild = CategoryFactory(parent=child, value="Grandchild")
        CategoryFactory(parent=root, value="Hidden", is_active=False)
        self.authenticate()

        response = self.client.get("/api/content/categories/tree/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["id"], root.id)
        self.assertEqual(set(response.data[0]), {"id", "slug", "title", "children"})
        self.assertEqual(response.data[0]["children"][0]["id"], child.id)
        self.assertEqual(response.data[0]["children"][0]["children"][0]["id"], grandchild.id)
        self.assertEqual(len(response.data[0]["children"]), 1)


class CountryListTests(ContentApiTestCase):
    def test_returns_countries(self):
        country = CountryFactory(slug="spain", short_slug="es", value="Spain")
        self.authenticate()

        response = self.client.get("/api/content/countries/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            {"id": country.id, "slug": "spain", "short_slug": "es", "title": "Spain"},
            response.data,
        )


class ContentPostTests(ContentApiTestCase):
    def setUp(self):
        super().setUp()
        self.root = CategoryFactory()
        self.rubric = CategoryFactory(parent=self.root, slug="grain")
        self.other_rubric = CategoryFactory(parent=self.root, slug="fruit")
        self.country = CountryFactory(slug="spain", short_slug="es", value="Spain")

    def test_lists_detailed_posts_and_filters_by_rubric_and_country(self):
        matching = PostFactory(
            publisher=self.user,
            rubric=self.rubric,
            country=self.country,
            source="source",
            sources="sources",
            meta_description="meta",
        )
        PhotoFactory(post=matching)
        PostFactory(rubric=self.other_rubric, country=self.country)
        PostFactory(rubric=self.rubric, country=CountryFactory(slug="france", short_slug="fr"))
        self.authenticate()

        response = self.client.get("/api/content/posts/?rubric=grain&country=es")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        result = response.data["results"][0]
        self.assertEqual(result["id"], matching.id)
        self.assertEqual(result["rubric"]["id"], self.rubric.id)
        self.assertEqual(result["country"]["id"], self.country.id)
        self.assertEqual(result["publisher"], self.user.id)
        self.assertEqual(len(result["photos"]), 1)
        self.assertIn("category_attributes", result)

    def test_page_size_is_configurable_and_capped_at_100(self):
        PostFactory.create_batch(105, rubric=self.rubric, publisher=self.user)
        self.authenticate()

        small_response = self.client.get("/api/content/posts/?page_size=3")
        capped_response = self.client.get("/api/content/posts/?page_size=1000")

        self.assertEqual(len(small_response.data["results"]), 3)
        self.assertEqual(len(capped_response.data["results"]), 100)

    def test_creates_post_for_token_owner(self):
        self.authenticate()

        response = self.client.post(
            "/api/content/posts/",
            {
                "title": "API post",
                "text": "Body",
                "rubric": self.rubric.id,
                "country": self.country.id,
                "source": "Publisher",
                "sources": "https://example.test/source",
                "author": "Author",
                "status": False,
                "publisher": UserFactory().id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        post = Post.objects.get(pk=response.data["id"])
        self.assertEqual(post.publisher, self.user)
        self.assertEqual(post.rubric, self.rubric)
        self.assertEqual(post.country, self.country)
        self.assertEqual(post.sources, "https://example.test/source")

    def test_create_requires_title_text_and_rubric(self):
        self.authenticate()

        response = self.client.post("/api/content/posts/", {}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.data), {"title", "text", "rubric"})

    def test_updates_only_token_owners_post(self):
        owned = PostFactory(publisher=self.user, rubric=self.rubric)
        other = PostFactory(rubric=self.rubric)
        attempted_publisher = UserFactory()
        self.authenticate()

        response = self.client.patch(
            f"/api/content/posts/{owned.id}/",
            {"title": "Updated", "publisher": attempted_publisher.id},
            format="json",
        )
        forbidden_response = self.client.patch(
            f"/api/content/posts/{other.id}/",
            {"title": "Not allowed"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        owned.refresh_from_db()
        self.assertEqual(owned.title, "Updated")
        self.assertEqual(owned.publisher, self.user)
        self.assertEqual(forbidden_response.status_code, 404)
        self.assertNotEqual(Category.objects.count(), 0)
