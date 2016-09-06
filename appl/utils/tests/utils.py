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
