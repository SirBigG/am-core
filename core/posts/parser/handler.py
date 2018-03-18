from core.posts.models import ParsedMap, Link, ParsedPost
from .parsers import PARSER_CLASSES


class ParseHandler(object):

    def __init__(self, map_instance):
        self.map = map_instance

    def create_links(self):
        for item in PARSER_CLASSES.get(self.map.type)(self.map):
            to_create = list()
            for i in item:
                i = self.get_link_item(i)
                if i:
                    to_create.append(i)
            Link.objects.bulk_create(to_create)

    def get_link_item(self, data):
        return Link(link=data['link'])

    def create_posts(self):
        for link in Link.objects.filter(is_parsed=False):
            item = PARSER_CLASSES.get(self.map.type)(self.map, link=link).get_item()
            ParsedPost(title=item['title'], original=item['text']).save()
            link.is_parsed = True
            link.save()
