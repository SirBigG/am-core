from lxml import html

from .base import BaseParser


class HtmlParser(BaseParser):

    def get_items(self):
        tree = html.fromstring(self.get_content())
        parsed = list()
        for i in tree.xpath(self.info.root):
            parsed.append({k: i.xpath(v)[0] for k, v in self.get_map().items()})
        return parsed

    def get_item(self):
        tree = html.fromstring(self.get_content())
        for i in tree.xpath(self.info.root):
            return {k: i.xpath(v)[0].text_content() for k, v in self.get_map().items()}


class HtmlIterParser(HtmlParser):
    def __init__(self, info):
        super().__init__(info)
        self.page = 1

    def __iter__(self):
        return self

    def __next__(self):
        response = self.get_response()
        if response.status_code == 200:
            self.page += 1
            return self.get_items()
        else:
            raise StopIteration

    def get_link(self):
        return super().get_link().format(self.page)
