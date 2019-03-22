from datetime import datetime

from django.views.generic import TemplateView
from django.conf import settings

from urllib import parse

from .models import News

import requests


class NewsListView(TemplateView):
    template_name = "news/list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        _url = f"{settings.API_HOST}/news"
        if self.request.GET.get("page"):
            _url = f"{_url}?page={self.request.GET.get('page')}"
        response = requests.get(_url)
        if response.status_code != 200:
            context["object_list"] = []
            return context

        # qs = News.objects.all()
        # if self.request.GET.get("from"):
        #    qs = qs.filter(date__gte=datetime.fromtimestamp(int(self.request.GET.get("from"))))
        news = response.json()
        _has_previous = False
        _has_next = False
        prev_page_number = None
        next_page_number = None
        if news.get("previous"):
            _has_previous = True
            prev_page_number = parse.parse_qs(parse.urlparse(news.get("previous")).query).get("page")[0]
        if news.get("next"):
            _has_next = True
            next_page_number = parse.parse_qs(parse.urlparse(news.get("next")).query).get("page")[0]
        context["object_list"] = news["items"]
        context["page_obj"] = {"previous_page_number": prev_page_number,
                               "has_previous": _has_previous,
                               "next_page_number": next_page_number,
                               "has_next": _has_next}
        context["paginator"] = {"num_pages": 2}
        return context


class AdvertListView(TemplateView):
    template_name = "news/advert_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        _url = f"{settings.API_HOST}/adverts"
        if self.request.GET.get("page"):
            _url = f"{_url}?page={self.request.GET.get('page')}"
        response = requests.get(_url)
        if response.status_code != 200:
            context["object_list"] = []
            return context

        # qs = News.objects.all()
        # if self.request.GET.get("from"):
        #    qs = qs.filter(date__gte=datetime.fromtimestamp(int(self.request.GET.get("from"))))
        adverts = response.json()
        _has_previous = False
        _has_next = False
        prev_page_number = None
        next_page_number = None
        if adverts.get("previous"):
            _has_previous = True
            prev_page_number = parse.parse_qs(parse.urlparse(adverts.get("previous")).query).get("page")[0]
        if adverts.get("next"):
            _has_next = True
            next_page_number = parse.parse_qs(parse.urlparse(adverts.get("next")).query).get("page")[0]
        context["object_list"] = adverts["items"]
        context["page_obj"] = {"previous_page_number": prev_page_number,
                               "has_previous": _has_previous,
                               "next_page_number": next_page_number,
                               "has_next": _has_next}
        context["paginator"] = {"num_pages": 2}
        return context
