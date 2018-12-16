from core.posts.models import Link, ParsedPost
from .parsers import PARSER_CLASSES


class ParseHandler(object):

    def __init__(self, map_instance):
        self.map = map_instance

    def create_links(self):
        for item in PARSER_CLASSES.get(self.map.type)(self.map):
            to_create = list()
            for i in item:
                if i:
                    to_create.append(i)
            Link.objects.bulk_create([Link(link=j["link"]) for j in set(to_create)])

    def create_posts(self):
        for link in Link.objects.filter(is_parsed=False):
            item = PARSER_CLASSES.get(self.map.type)(self.map, link=link).get_item()
            if item:
                ParsedPost(title=item['title'], original=item["type"] + item['text']).save()
                link.is_parsed = True
                link.save()
