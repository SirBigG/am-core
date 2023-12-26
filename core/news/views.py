import http
from datetime import datetime

from django.http import Http404
from django.views.generic import TemplateView
from django.conf import settings

from urllib import parse

from core.classifier.models import Category

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


class NewsDetailView(TemplateView):
    template_name = "news/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        _slug = kwargs.get("slug")
        _id = kwargs.get("pk")
        _url = f"{settings.API_HOST}/news/{_id}"
        response = requests.get(_url)
        if response.status_code == http.HTTPStatus.NOT_FOUND:
            raise Http404

        if response.status_code != 200:
            context["object"] = None
            return context
        data = response.json()
        data["url"] = f"{settings.HOST}/news/{_slug}-{_id}.html"
        context["object"] = data
        return context


class AdvertListView(TemplateView):
    template_name = "news/advert_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        _category = kwargs.get('category')
        if _category:
            if _category == "other":
                class Cat:
                    id = 0
                    value = "Інше"

                _category = Cat
            else:
                _category = Category.objects.get(slug=_category)
        _url = f"{settings.API_HOST}/adverts"
        if self.request.GET.get("page"):
            _url = f"{_url}?page={self.request.GET.get('page')}"
            if _category:
                _url = f"{_url}&category={_category.id}"
        else:
            if _category:
                _url = f"{_url}?category={_category.id}"
        response = requests.get(_url)
        if response.status_code != 200:
            context["object_list"] = []
            return context

        adverts = response.json()
        _has_previous = False
        _has_next = False
        prev_page_number = None
        next_page_number = None
        if adverts.get("previous") and parse.parse_qs(parse.urlparse(adverts.get("previous")).query).get("page"):
            _has_previous = True
            prev_page_number = parse.parse_qs(parse.urlparse(adverts.get("previous")).query).get("page")[0]
        if adverts.get("next") and parse.parse_qs(parse.urlparse(adverts.get("next")).query).get("page"):
            _has_next = True
            next_page_number = parse.parse_qs(parse.urlparse(adverts.get("next")).query).get("page")[0]
        context["object_list"] = adverts["items"]
        context["page_obj"] = {"previous_page_number": prev_page_number,
                               "has_previous": _has_previous,
                               "next_page_number": next_page_number,
                               "has_next": _has_next}
        context["paginator"] = {"num_pages": 2}
        context["category"] = _category
        return context


class NewsSitemapView(TemplateView):
    template_name = "sitemap.xml"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        _url = f"{settings.API_HOST}/news/sitemap"
        response = requests.get(_url)
        if response.status_code != 200:
            context["urls"] = []
            return context
        news = response.json()
        context["urls"] = [{
            "loc": item["loc"], "lastmod": datetime.fromisoformat(item["lastmod"])} for item in news["items"]]
        return context
