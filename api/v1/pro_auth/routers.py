from rest_framework.routers import SimpleRouter, Route


class ProfileRouter(SimpleRouter):
    routes = [Route(
            url=r'^{prefix}{trailing_slash}$',
            mapping={
                'get': 'retrieve',
                'put': 'update',
                'patch': 'partial_update',
                'delete': 'destroy'
            },
            name='{basename}-detail',
            initkwargs={'suffix': 'Instance'},
            detail=True
        )]

    def get_lookup_regex(self, viewset, lookup_prefix=''):
        base_regex = '(?P<{lookup_prefix}{lookup_url_kwarg}>{lookup_value})'
        return base_regex.format(
            lookup_prefix='',
            lookup_url_kwarg='',
            lookup_value=''
        )
