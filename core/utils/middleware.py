from django.conf import settings


class SecurityMiddleware(object):
    def process_request(self, request):
        # Now spike for https urls makes
        # TODO: need to setting nginx well
        if not request.META.get(settings.SECURE_PROXY_SSL_HEADER[0]):
            request.META[settings.SECURE_PROXY_SSL_HEADER[0]] = 'https'
