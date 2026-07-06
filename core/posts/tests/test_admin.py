from ckeditor.widgets import CKEditorWidget
from django.contrib import admin
from django.contrib.auth.models import Permission
from django.test import RequestFactory, TestCase

from core.posts.admin import AdminPostForm, PostAdmin
from core.posts.category_attributes import attribute_form_field_name
from core.posts.models import CategoryAttributeFieldType, Post, PostAttributeValue
from core.utils.tests.factories import (
    CategoryAttributeChoiceFactory,
    CategoryAttributeFieldFactory,
    CategoryAttributeGroupFactory,
    CategoryFactory,
    PostFactory,
    StaffUserFactory,
)


class AdminPostFormTests(TestCase):
    def test_sources_uses_ckeditor_widget(self):
        form = PostAdmin.form()

        self.assertIsInstance(form.fields["sources"].widget, CKEditorWidget)

    def test_category_attribute_fields_load_from_instance(self):
        category = CategoryFactory()
        group = CategoryAttributeGroupFactory(category=category, title="Fruits")
        ripening = CategoryAttributeFieldFactory(category=category, group=group, key="ripening", label="Ripening")
        taste = CategoryAttributeFieldFactory(
            category=category,
            group=group,
            key="taste",
            label="Taste",
            field_type=CategoryAttributeFieldType.MULTISELECT,
        )
        CategoryAttributeChoiceFactory(field=ripening, value="winter", label="Winter")
        CategoryAttributeChoiceFactory(field=taste, value="sweet", label="Sweet")
        post = PostFactory(
            rubric=category,
            category_attributes={str(category.pk): {"ripening": "winter", "taste": ["sweet"]}},
        )

        form_class = type("TestAdminPostForm", (AdminPostForm,), {"category_attribute_fields": (ripening, taste)})
        form = form_class(instance=post)

        self.assertEqual(form.fields[attribute_form_field_name(ripening)].initial, "winter")
        self.assertEqual(form.fields[attribute_form_field_name(taste)].initial, ["sweet"])

    def test_category_attribute_fields_save_to_json_and_index(self):
        category = CategoryFactory()
        group = CategoryAttributeGroupFactory(category=category)
        ripening = CategoryAttributeFieldFactory(category=category, group=group, key="ripening")
        color = CategoryAttributeFieldFactory(
            category=category,
            group=group,
            key="color",
            field_type=CategoryAttributeFieldType.MULTISELECT,
        )
        CategoryAttributeChoiceFactory(field=ripening, value="winter", label="Winter")
        CategoryAttributeChoiceFactory(field=color, value="red", label="Red")
        CategoryAttributeChoiceFactory(field=color, value="green", label="Green")
        post = PostFactory(rubric=category, category_attributes={str(category.pk): {"unknown_future_key": "keep-me"}})
        request = RequestFactory().post("/")
        request.user = StaffUserFactory()
        model_admin = PostAdmin(Post, admin.site)
        form_class = model_admin.get_form(request, obj=post)
        data = {
            "title": post.title,
            "text": post.text,
            "publisher": post.publisher_id,
            "rubric": category.pk,
            "publish_date_0": post.publish_date.strftime("%Y-%m-%d"),
            "publish_date_1": post.publish_date.strftime("%H:%M:%S"),
            "update_date_0": post.update_date.strftime("%Y-%m-%d"),
            "update_date_1": post.update_date.strftime("%H:%M:%S"),
            "status": "on",
            "tags": "",
            attribute_form_field_name(ripening): "winter",
            attribute_form_field_name(color): ["red", "green"],
        }

        form = form_class(data=data, instance=post)

        self.assertTrue(form.is_valid(), form.errors)
        saved_post = form.save()
        self.assertEqual(
            saved_post.category_attributes,
            {
                str(category.pk): {
                    "unknown_future_key": "keep-me",
                    "ripening": "winter",
                    "color": ["red", "green"],
                },
            },
        )
        self.assertEqual(PostAttributeValue.objects.filter(post=saved_post).count(), 3)

    def test_category_change_preserves_old_json_and_rebuilds_current_index(self):
        old_rubric = CategoryFactory()
        new_rubric = CategoryFactory()
        old_field = CategoryAttributeFieldFactory(category=old_rubric, key="old_attribute")
        new_field = CategoryAttributeFieldFactory(category=new_rubric, key="new_attribute")
        CategoryAttributeChoiceFactory(field=old_field, value="old", label="Old")
        CategoryAttributeChoiceFactory(field=new_field, value="new", label="New")
        post = PostFactory(
            rubric=old_rubric,
            category_attributes={str(old_rubric.pk): {"old_attribute": "old"}},
        )
        request = RequestFactory().post("/", {"rubric": new_rubric.pk})
        request.user = StaffUserFactory()
        model_admin = PostAdmin(Post, admin.site)
        form_class = model_admin.get_form(request, obj=post)
        data = {
            "title": post.title,
            "text": post.text,
            "publisher": post.publisher_id,
            "rubric": new_rubric.pk,
            "publish_date_0": post.publish_date.strftime("%Y-%m-%d"),
            "publish_date_1": post.publish_date.strftime("%H:%M:%S"),
            "update_date_0": post.update_date.strftime("%Y-%m-%d"),
            "update_date_1": post.update_date.strftime("%H:%M:%S"),
            "status": "on",
            "tags": "",
            attribute_form_field_name(new_field): "new",
        }

        form = form_class(data=data, instance=post)

        self.assertTrue(form.is_valid(), form.errors)
        saved_post = form.save()
        self.assertEqual(
            saved_post.category_attributes,
            {
                str(old_rubric.pk): {"old_attribute": "old"},
                str(new_rubric.pk): {"new_attribute": "new"},
            },
        )
        self.assertEqual(PostAttributeValue.objects.get(post=saved_post).field, new_field)


class PostAdminTests(TestCase):
    def grant_permission(self, user, codename):
        permission = Permission.objects.get(codename=codename)
        user.user_permissions.add(permission)

    def build_request(self, user):
        request = RequestFactory().get("/")
        request.user = user
        return request

    def test_category_attributes_render_in_one_fieldset(self):
        category = CategoryFactory()
        first_group = CategoryAttributeGroupFactory(category=category, title="Fruits")
        second_group = CategoryAttributeGroupFactory(category=category, title="Taste")
        first_field = CategoryAttributeFieldFactory(category=category, group=first_group)
        second_field = CategoryAttributeFieldFactory(category=category, group=second_group)
        post = PostFactory(rubric=category)
        request = RequestFactory().get("/")
        request.user = StaffUserFactory()
        model_admin = PostAdmin(Post, admin.site)

        fieldsets = model_admin.get_fieldsets(request, obj=post)

        category_fieldsets = [fieldset for fieldset in fieldsets if fieldset[0] == "Category attributes"]
        self.assertEqual(len(category_fieldsets), 1)
        self.assertEqual(
            category_fieldsets[0][1]["fields"],
            (attribute_form_field_name(first_field), attribute_form_field_name(second_field)),
        )

    def test_source_mode_assets_are_included(self):
        model_admin = PostAdmin(Post, admin.site)
        media = str(model_admin.media)

        self.assertIn("posts/admin/ckeditor-source.css", media)
        self.assertIn("posts/admin/ckeditor-source.js", media)
        self.assertNotIn("posts/admin/apple-variety-attributes.css", media)
        self.assertNotIn("posts/admin/apple-variety-attributes.js", media)

    def test_own_post_permission_limits_changelist_to_owned_posts(self):
        staff_user = StaffUserFactory()
        own_post = PostFactory(publisher=staff_user, title="Own post")
        other_post = PostFactory(title="Other post")
        self.grant_permission(staff_user, "change_own_post")
        request = self.build_request(staff_user)
        model_admin = PostAdmin(Post, admin.site)

        queryset = model_admin.get_queryset(request)

        self.assertIn(own_post, queryset)
        self.assertNotIn(other_post, queryset)

    def test_own_post_permission_allows_only_owned_object_view_and_change(self):
        staff_user = StaffUserFactory()
        own_post = PostFactory(publisher=staff_user)
        other_post = PostFactory()
        self.grant_permission(staff_user, "change_own_post")
        request = self.build_request(staff_user)
        model_admin = PostAdmin(Post, admin.site)

        self.assertTrue(model_admin.has_view_permission(request))
        self.assertTrue(model_admin.has_change_permission(request))
        self.assertTrue(model_admin.has_view_permission(request, own_post))
        self.assertTrue(model_admin.has_change_permission(request, own_post))
        self.assertFalse(model_admin.has_view_permission(request, other_post))
        self.assertFalse(model_admin.has_change_permission(request, other_post))

    def test_global_post_permission_keeps_full_changelist_access(self):
        staff_user = StaffUserFactory()
        own_post = PostFactory(publisher=staff_user)
        other_post = PostFactory()
        self.grant_permission(staff_user, "view_post")
        request = self.build_request(staff_user)
        model_admin = PostAdmin(Post, admin.site)

        queryset = model_admin.get_queryset(request)

        self.assertIn(own_post, queryset)
        self.assertIn(other_post, queryset)

    def test_own_post_permission_forces_publisher_to_current_user_on_save(self):
        staff_user = StaffUserFactory()
        submitted_publisher = StaffUserFactory()
        post = PostFactory.build(publisher=submitted_publisher, rubric=CategoryFactory())
        self.grant_permission(staff_user, "change_own_post")
        request = self.build_request(staff_user)
        model_admin = PostAdmin(Post, admin.site)

        model_admin.save_model(request, post, form=None, change=False)

        post.refresh_from_db()
        self.assertEqual(post.publisher, staff_user)
