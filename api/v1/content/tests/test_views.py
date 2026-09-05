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

    def test_staff_token_updates_any_post_without_changing_publisher(self):
        self.user.is_staff = True
        self.user.save(update_fields=("is_staff",))
        owned = PostFactory(publisher=self.user, rubric=self.rubric)
        other = PostFactory(rubric=self.rubric)
        attempted_publisher = UserFactory()
        original_other_publisher = other.publisher
        self.authenticate()

        response = self.client.patch(
            f"/api/content/posts/{owned.id}/",
            {"title": "Updated", "publisher": attempted_publisher.id},
            format="json",
        )
        other_response = self.client.patch(
            f"/api/content/posts/{other.id}/",
            {"title": "Staff edited", "publisher": attempted_publisher.id},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(other_response.status_code, 200, other_response.data)
        owned.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(owned.title, "Updated")
        self.assertEqual(owned.publisher, self.user)
        self.assertEqual(other.title, "Staff edited")
        self.assertEqual(other.publisher, original_other_publisher)
        self.assertNotEqual(Category.objects.count(), 0)

    def test_non_staff_token_cannot_retrieve_or_update_posts(self):
        post = PostFactory(publisher=self.user, rubric=self.rubric)
        self.authenticate()

        get_response = self.client.get(f"/api/content/posts/{post.id}/")
        patch_response = self.client.patch(
            f"/api/content/posts/{post.id}/",
            {"title": "Not allowed"},
            format="json",
        )

        self.assertEqual(get_response.status_code, 403)
        self.assertEqual(patch_response.status_code, 403)
        post.refresh_from_db()
        self.assertNotEqual(post.title, "Not allowed")

    def test_creates_optional_metadata_and_returns_resolved_values(self):
        self.authenticate()
        for fields in ({}, {"meta_title": "Заголовок сторінки", "meta_description": "Опис сторінки"}):
            response = self.client.post(
                "/api/content/posts/",
                {
                    "title": "Канонічна назва",
                    "text": "<p>Текст статті.</p>",
                    "rubric": self.rubric.pk,
                    **fields,
                },
                format="json",
            )
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(
                response.data["resolved_metadata"],
                {
                    "title": fields.get("meta_title", "Канонічна назва"),
                    "description": fields.get("meta_description", "Текст статті."),
                },
            )
            post = Post.objects.get(pk=response.data["id"])
            self.assertIsNone(post.meta_id)
            self.assertEqual(post.title, "Канонічна назва")

    def test_staff_updates_and_clears_metadata_without_changing_identity(self):
        post = PostFactory(rubric=self.rubric, title="Гала", meta_description="Existing", meta_title="Existing title")
        original_url = post.get_absolute_url()
        original_slug, original_publisher = post.slug, post.publisher_id
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        self.authenticate()
        response = self.client.patch(
            f"/api/content/posts/{post.pk}/", {"meta_title": "Гала: характеристики"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["meta_description"], "Existing")
        self.assertEqual(response.data["resolved_metadata"]["title"], "Гала: характеристики")
        for clear in ("", None, "   "):
            response = self.client.patch(
                f"/api/content/posts/{post.pk}/",
                {
                    "meta_title": clear,
                    "meta_description": clear,
                },
                format="json",
            )
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["resolved_metadata"], {"title": "Гала", "description": post.text})
        post.refresh_from_db()
        self.assertEqual(
            (post.title, post.slug, post.get_absolute_url(), post.publisher_id),
            ("Гала", original_slug, original_url, original_publisher),
        )
        detail = self.client.get(f"/api/content/posts/{post.pk}/")
        listing = self.client.get("/api/content/posts/")
        self.assertEqual(detail.data["resolved_metadata"], listing.data["results"][0]["resolved_metadata"])

    def test_metadata_length_validation_and_staff_requirement(self):
        post = PostFactory(rubric=self.rubric)
        self.authenticate()
        response = self.client.patch(f"/api/content/posts/{post.pk}/", {"meta_title": "Unauthorized"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        response = self.client.patch(
            f"/api/content/posts/{post.pk}/",
            {
                "meta_title": "x" * 501,
                "meta_description": "x" * 501,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.data), {"meta_title", "meta_description"})
        post.refresh_from_db()
        self.assertIsNone(post.meta_title)

    def test_options_describes_optional_metadata_for_integrations(self):
        self.authenticate()
        response = self.client.options("/api/content/posts/")
        self.assertEqual(response.status_code, 200)
        fields = response.data["actions"]["POST"]
        for field in ("meta_title", "meta_description"):
            self.assertFalse(fields[field]["required"])
            self.assertEqual(fields[field]["max_length"], 500)
        self.assertTrue(fields["resolved_metadata"]["read_only"])
