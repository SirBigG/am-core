from lxml import html

from io import BytesIO
from PIL import Image

from django.core.files.uploadedfile import SimpleUploadedFile


def make_image(params=None):
    """Creating fake image for image upload testing.
    :return: in memory image file """
    params = dict() if params is None else params
    width = params.get('width', 100)
    height = params.get('height', width)
    color = params.get('color', 'blue')
    image_format = params.get('format', 'JPEG')

    file = BytesIO()
    Image.new('RGB', (width, height), color).save(file, image_format)
    file.seek(0)
    return SimpleUploadedFile('test.jpg', file.getvalue(), content_type="image/jpg")


class HtmlTestCaseMixin(object):
    """Implementing some asserts methods for testing marking."""
    @staticmethod
    def _parse(h_str):
        """Parse html string."""
        return html.fromstring(h_str)

    def assertClassIn(self, class_name, s, msg=None):
        """Check that class name in html string."""
        if not self._parse(s).find_class(class_name):
            msg = self._formatMessage(msg, "Class '%s', not in html string." % class_name)
            raise self.failureException(msg)

    def assertEqualClassCount(self, s, class_name, count, msg=None):
        """Check count of elements with class_name"""
        c = len(self._parse(s).find_class(class_name))
        if c != count:
            msg = self._formatMessage(msg, "%s != %s" % (c, count))
            raise self.failureException(msg)

    def assertIdIn(self, el_id, s, msg=None):
        """Check that element with id in html string."""
        try:
            self._parse(s).get_element_by_id(el_id)
        except KeyError:
            msg = self._formatMessage(msg, "Id '%s', not in html string." % el_id)
            raise self.failureException(msg)

    def _get_head_tag(self, s, tag_name, meta_name=None):
        """Getting element from head."""
        head_list = self._parse(s).head.getchildren()
        for i in head_list:
            if tag_name == "title" and i.tag == "title":
                return i
            elif tag_name == "meta" and meta_name and i.tag == "meta":
                for name, value in i.items():
                    if name == "name" and value == meta_name:
                        return i
        return None

    def _assert_head_tag_in(self, tag, name, msg=None):
        if tag is None:
            msg = self._formatMessage(msg, "'%s' doesn't found." % name)
            raise self.failureException(msg)

    def assertTitleIn(self, s, msg=None):
        title = self._get_head_tag(s, 'title')
        self._assert_head_tag_in(title, 'title', msg)

    def assertTitleNotEmpty(self, s, msg=None):
        title = self._get_head_tag(s, 'title')
        self._assert_head_tag_in(title, 'title', msg)
        if not title.text_content():
            msg = self._formatMessage(msg, "Title is empty.")
            raise self.failureException(msg)

    def assertEqualTitleValue(self, s, value, msg=None):
        title = self._get_head_tag(s, 'title')
        self._assert_head_tag_in(title, 'title', msg)
        if title.text_content() != value:
            msg = self._formatMessage(msg, "'%s' != '%s'" % (title.text_content(), value))
            raise self.failureException(msg)

    def assertMetaTagIn(self, s, name, msg=None):
        meta = self._get_head_tag(s, 'meta', name)
        self._assert_head_tag_in(meta, name, msg)

    def assertMetaTagContentNotEmpty(self, s, name, msg=None):
        meta = self._get_head_tag(s, 'meta', name)
        self._assert_head_tag_in(meta, name, msg)
        for n, v in meta.items():
            if n == 'content' and not v:
                msg = self._formatMessage(msg, "Meta '%s' is empty." % name)
                raise self.failureException(msg)

    def assertEqualMetaTagContent(self, s, name, content, msg=None):
        """Compare content of head meta tag."""
        meta = self._get_head_tag(s, 'meta', name)
        self._assert_head_tag_in(meta, name, msg)
        for n, v in meta.items():
            if n == 'content' and v != content:
                msg = self._formatMessage(msg, "'%s' != '%s'" % (v, content))
                raise self.failureException(msg)

    def assertMetaDataNotEnpty(self, s):
        """Check base meta tags not empty values."""
        self.assertTitleNotEmpty(s)
        self.assertMetaTagContentNotEmpty(s, 'description')

    def assertMetaDataIn(self, s):
        """Check base meta tags in page."""
        self.assertTitleIn(s)
        self.assertMetaTagIn(s, 'description')

    def assertH1(self, s, msg=None):
        """Check if h1 present in body block and if more than one tag in page."""
        desc = self._parse(s).iterdescendants()
        n = len([h1 for h1 in desc if h1.tag == 'h1'])
        if n == 0:
            msg = self._formatMessage(msg, "H1 tag doesn't found.")
            raise self.failureException(msg)
        elif n > 1:
            msg = self._formatMessage(msg, "You have more than one H1 tag.")
            raise self.failureException(msg)
