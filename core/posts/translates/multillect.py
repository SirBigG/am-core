import requests

from django.conf import settings

from core.posts.models import ParsedPost


API_URL = "https://api.multillect.com/translate/json/1.0/{}".format(settings.MULTILLECT_ACCOUNT_ID)


def translate():
    base_body = {
        'method': 'translate/api/translate',
        'from': 'ru', 'to': 'uk',
        'sig': settings.MULTILLECT_SECRET_KEY, 'text': ''}
    for i in ParsedPost.objects.filter(is_translated=False):
        try:
            base_body['text'] = i.original
            response = requests.post(API_URL, data=base_body)
            if response.status_code == 200:
                i.translated = response.json().get('result').get('translated')
                i.is_translated = True
                i.save()
        except Exception as e:
            print(e)
