import requests
import json


class BaseParser(object):
    host_attr = 'host'
    link_attr = 'link'
    client = requests

    def __init__(self, info, link=None):
        self.info = info
        self.link = link

    def get_map(self):
        return json.loads(self.info.map)

    def get_link(self):
        return self.link if self.link else getattr(self.info, self.host_attr) + getattr(self.info, self.link_attr)

    def get_response(self):
        return self.client.get(self.get_link())

    def get_content(self):
        return self.get_response().content

    def get_items(self):
        raise NotImplementedError

    @property
    def items(self):
        return self.get_items()
