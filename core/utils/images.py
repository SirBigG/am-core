import base64
import hashlib
import hmac
from uuid import uuid4

from django.conf import settings


def unique_image_name(prefix="image", extension="jpg"):
    return f"{prefix}-{uuid4().hex}.{extension.lstrip('.')}"


def imgproxy_url(image_url, width, height, resize_type="fit", output_format="webp"):
    if not settings.USE_IMGPROXY:
        return image_url

    key = bytes.fromhex(settings.IMGPROXY_KEY)
    salt = bytes.fromhex(settings.IMGPROXY_SALT)
    base_url = settings.IMGPROXY_BASE_URL

    encoded_url = base64.urlsafe_b64encode(image_url.encode()).rstrip(b"=").decode()
    path = f"/rs:{resize_type}:{width}:{height}:f:0/{encoded_url}.{output_format}"
    path_b = path.encode()

    signature = hmac.new(key, salt + path_b, hashlib.sha256).digest()

    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
    return f"{base_url}/{encoded_signature}{path}"
