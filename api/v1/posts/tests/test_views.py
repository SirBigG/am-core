from core.classifier.models import Category
from core.posts.models import Photo, Post, UsefulStatistic
from core.utils.tests.factories import CategoryFactory, PhotoFactory, PostFactory, UserFactory
from core.utils.tests.utils import make_image
from rest_framework.test import APIClient, APITestCase

api_client = APIClient()


class ApiPostListTests(APITestCase):
    def setUp(self):
        root = CategoryFactory()
        parent = CategoryFactory(parent=root)
        self.child = CategoryFactory(parent=parent)
        for i in range(5):
            post = PostFactory(rubric=self.child)
            PhotoFactory(post=post)

    def tearDown(self):
        for i in Photo.objects.all():
            i.delete()

    def test_response(self):
        response = api_client.get("/api/post/all/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data), {"count", "next", "previous", "results"})
        self.assertEqual(set(response.data["results"][0]), {"title", "text", "url", "photo"})
        self.assertEqual(set(response.data["results"][0]["photo"]), {"description", "author", "source", "image"})

    def test_pagination(self):
        PostFactory.create_batch(20, **{"rubric": self.child})
        PostFactory(status=0, rubric=self.child)
        response = api_client.get("/api/post/all/", format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertEqual(response.data["count"], 25)
        self.assertEqual(response.data["next"], "http://testserver/api/post/all/?page=2")
        response = api_client.get("/api/post/all/?page=2", format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 10)


class RandomApiPostListTests(APITestCase):
    def setUp(self):
        root = CategoryFactory()
        parent = CategoryFactory(parent=root)
        child = CategoryFactory(parent=parent)
        PostFactory.create_batch(7, **{"rubric": child})

    def test_response(self):
        response = api_client.get("/api/post/random/all/", format="json")
        self.assertEqual(response.status_code, 200)

    def test_pagination(self):
        response = api_client.get("/api/post/random/all/", format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 4)
        self.assertEqual(response.data["count"], 7)
        self.assertEqual(response.data["next"], "http://testserver/api/post/random/all/?page=2")
        response = api_client.get("/api/post/random/all/?page=2", format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 3)


class UserPostsViewSetTests(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.user.set_password("12345")
        self.user.save()
        root = CategoryFactory()
        parent = CategoryFactory(parent=root)
        child = CategoryFactory(parent=parent)
        self.post = PostFactory(publisher=self.user, rubric=child)

    def test_return_post(self):
        api_client.login(email=self.user.email, password="12345")
        response = api_client.get("/api/user/posts/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

    def test_not_autorized(self):
        response = api_client.get("/api/user/posts/")
        self.assertEqual(response.status_code, 403)

    def test_detail_post(self):
        PhotoFactory(post=self.post)
        api_client.login(email=self.user.email, password="12345")
        response = api_client.get("/api/user/posts/%s/" % self.post.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.data),
            {"title", "text", "source", "status", "rubric", "url", "photo"},
        )
        self.assertEqual(response.data["rubric"], {"pk": self.post.rubric.pk, "value": str(self.post.rubric)})
        self.assertEqual(set(response.data["photo"]), {"description", "author", "source", "image"})
        self.assertTrue(response.data["status"])

    def test_only_returns_posts_for_authenticated_user(self):
        other_user = UserFactory()
        PostFactory(publisher=other_user, rubric=self.post.rubric)
        api_client.login(email=self.user.email, password="12345")

        response = api_client.get("/api/user/posts/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["title"], self.post.title)

    def test_create_post_requires_photos(self):
        root = CategoryFactory()
        parent = CategoryFactory(parent=root)
        api_client.login(email=self.user.email, password="12345")
        response = api_client.post(
            "/api/user/posts/",
            data={"title": "тайтл", "text": "text", "rubric": parent.pk},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("photos", response.data)

    def test_creating_post_by_user(self):
        root = CategoryFactory()
        parent = CategoryFactory(parent=root, slug="pigeon")
        api_client.login(email=self.user.email, password="12345")
        response = api_client.post(
            "/api/user/posts/",
            data=dict(title="тайтл", text="text", photos=[make_image(), make_image()], rubric=parent.pk),
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Post.objects.filter(publisher=self.user).count(), 2)
        self.assertEqual(Post.objects.get(title="тайтл").slug, "tajtl")
        self.assertEqual(Post.objects.get(title="тайтл").status, 0)
        self.assertEqual(Photo.objects.count(), 2)
        # Test creating user category for parent
        self.assertTrue(Category.objects.get(slug="pigeon-user"))
        # Test returns url for created post
        response = api_client.get(response.data["url"])
        self.assertEqual(response.status_code, 200)


class PostViewTests(APITestCase):
    def setUp(self):
        self.post = PostFactory()

    def test_create_view_instance(self):
        self.assertEqual(Post.objects.get(pk=self.post.pk).hits, 0)
        response = self.client.post("/api/post/view/", data={"fingerprint": "fingerprint", "post_id": self.post.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Post.objects.get(pk=self.post.pk).hits, 1)
        # Current behavior tracks every view request.
        response = self.client.post("/api/post/view/", data={"fingerprint": "fingerprint", "post_id": self.post.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Post.objects.get(pk=self.post.pk).hits, 2)


class PostUsefulViewTests(APITestCase):
    def test_records_useful_vote_once_for_same_payload(self):
        payload = {"fingerprint": "fingerprint", "post_id": 42, "is_useful": True}

        response = self.client.post("/api/post/useful/", data=payload, format="json")
        second_response = self.client.post("/api/post/useful/", data=payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(response.data, {"code": 200, "message": "Success"})
        self.assertEqual(UsefulStatistic.objects.count(), 1)
