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


class DisableAutoAdd(object):
    """Context manager for off auto_now_add date for tests and back it.
       Example: with DisableAutoAdd(*[Model1, Model2]):
                    # Do something
    """
    def __init__(self, *models):
        self.models = models

    def change_auto_now_fields(self, status):
        """Turns off the auto_now and auto_now_add attributes on a Model's fields,
            so that an instance of the Model can be saved with a custom value.
            """
        for model in self.models:
            for field in model._meta.local_fields:
                if hasattr(field, 'auto_now'):
                    field.auto_now = status
                if hasattr(field, 'auto_now_add'):
                    field.auto_now_add = status

    def __enter__(self):
        self.change_auto_now_fields(False)

    def __exit__(self, type, value, traceback):
        self.change_auto_now_fields(True)
