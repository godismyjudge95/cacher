from ConfigParser import SafeConfigParser
import logging
import requests
import time
import os

from ulauncher.api.client.Extension import Extension
from ulauncher.api.client.EventListener import EventListener
from ulauncher.api.shared.event import KeywordQueryEvent, ItemEnterEvent
from ulauncher.api.shared.item.ExtensionResultItem import ExtensionResultItem
from ulauncher.api.shared.action.RenderResultListAction import RenderResultListAction
from ulauncher.api.shared.action.CopyToClipboardAction import CopyToClipboardAction

logging.basicConfig()
logger = logging.getLogger(__name__)

parser = SafeConfigParser()
ext_path = os.path.dirname(os.path.abspath(__file__))
parser.read(ext_path + '/config.ini')


class KeywordQueryEventListener(EventListener):
    def on_event(self, event, extension):
        items = extension.get_items(event.get_argument())
        return RenderResultListAction(items)


class Cacher(Extension):
    matches_len = 0

    def __init__(self):

        key = parser.get('General', 'key')
        token = parser.get('General', 'token')

        if not key or not token:
            logger.error('Credentials are not found!')

        self.cache_max = 3600
        self.cache_start = time.time()
        self.data = None
        self.headers = {'X-Api-Key': key, 'X-Api-Token': token}
        super(Cacher, self).__init__()
        self.subscribe(KeywordQueryEvent, KeywordQueryEventListener())

    @staticmethod
    def get_labels(label, guid):
        lbs = []
        for i in range(0, len(label)):
            for j in range(0, len(label[i]['snippets'])):
                if label[i]['snippets'][j]['guid'] == guid:
                    lbs.append('(' + label[i]['title'] + ') ')
                    break
        return lbs

    def find_rec(self, data, query, matches):

        for i in range(0, len(data)):

            if len(data[i]['files']) > 0:

                if self.matches_len >= 10:
                    return matches

                res_tit = data[i]['title'].lower().find(query, 0, len(data[i]['title']))
                res_desc = data[i]['description'].lower().find(query, 0, len(data[i]['description']))

                if res_tit != -1 or res_desc != -1:
                    matches.append({'guid': data[i]['guid'],
                                    'title': data[i]['title'].encode('utf8'),
                                    'data': data[i]['files'][0]['content'].encode('utf8'),
                                    'file': data[i]['files'][0]['filename'].encode('utf8')})
                    self.matches_len += 1
                    continue

                for j in range(0, len(data[i]['files'])):

                    res_cont = data[i]['files'][j]['content'].lower().find(query, 0,
                                                                           len(data[i]['files'][j]['content']))
                    res_file = data[i]['files'][j]['filename'].lower().find(query, 0,
                                                                            len(data[i]['files'][j]['filename']))

                    if res_cont != -1 or res_file != -1:
                        matches.append({'guid': data[i]['guid'],
                                        'title': data[i]['title'].encode('utf8'),
                                        'data': data[i]['files'][j]['content'].encode('utf8'),
                                        'file': data[i]['files'][j]['filename'].encode('utf8')})
                        self.matches_len += 1

        return matches

    def get_items(self, query):

        items = []

        if self.data is None or (time.time() - self.cache_start) > self.cache_max:
            response = requests.get('https://api.cacher.io/integrations/show_all', headers=self.headers)
            self.data = response.json()

            if 'status' in self.data and self.data['status'] == 'error':
                logger.error(self.data['message'])

        matches = []
        self.matches_len = 0

        if query is None:
            query = ''

        matches = self.find_rec(self.data['personalLibrary']['snippets'], query, matches)

        for i in range(0, self.matches_len):
            labels = self.get_labels(self.data['personalLibrary']['labels'], matches[i]['guid'])
            items.append(ExtensionResultItem(icon='images/cacher.png',
                                             name='%s' % matches[i]['title'],
                                             description='%s' % matches[i]['file'] + ' ' + ''.join(labels),
                                             on_enter=CopyToClipboardAction(matches[i]['data'])))

        return items