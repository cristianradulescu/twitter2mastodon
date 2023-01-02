import requests
from logging import Logger


class MastodonApiConfig:
    def __init__(self, config):
        self.base_url = config['base_url']
        self.auth_token = config['auth_token']


class MastodonApi:
    def __init__(self, config: MastodonApiConfig, logger: Logger = None):
        self.config = config
        if logger is None:
            self.logger = Logger
        else:
            self.logger = logger
        self.errors = []

    def do_request(self, url, headers=None):
        try:
            if headers is None:
                headers = {'Authorization': f'Bearer {self.config.auth_token}'}
            return requests.get(url=url, headers=headers, timeout=5)
        except Exception as e:
            self.logger.error(f'Unexpected error occurred. Error details: {e}')
            return None

    def response_has_errors(self, response):
        return 'error' in response or 'accounts' not in response or ('accounts' in response and len(response['accounts']) == 0)

    def collect_response_errors(self, response):
        if 'error' in response:
            self.errors.append(response['error'])
        elif 'accounts' not in response or ('accounts' in response and len(response['accounts']) == 0):
            self.errors.append('Not found')

    def find_mastodon_user_by_username(self, username):
        """
        Assume there are no duplicates
        """
        self.logger.debug(f'Mastodon username {username}')
        response = self.do_request(f'{self.config.base_url}/search?q={username}')

        if response is None:
            return None

        mastodon_user_data = response.json()
        if self.response_has_errors(mastodon_user_data):
            self.collect_response_errors(mastodon_user_data)
            self.logger.debug('Mastodon response has errors')
            return None

        return mastodon_user_data['accounts'][0]
