from datetime import datetime, timedelta

from django.conf import settings

from rest_framework.views import APIView
from rest_framework.response import Response

from core.news.models import News


class CreateNewsView(APIView):
    def post(self, request, *args, **kwargs):
        News.objects.bulk_create([News(title=item.get('title'),
                                       link=item.get('link'),
                                       poster=item.get('poster')) for item in request.data["items"]])
        return Response({"link":
                             f"{settings.HOST}/news/"
                             f"?from={int((datetime.now() - timedelta(days=1)).timestamp())}"
                             f"&to={int(datetime.now().timestamp())}"
                         })
