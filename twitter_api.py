import requests
from logging import Logger


class TwitterApiConfig:
    def __init__(self, config):
        self.base_url = config['base_url']
        self.auth_token = config['auth_token']
        self.max_results = config['max_results']


class TwitterApi:
    def __init__(self, config: TwitterApiConfig, logger: Logger = None):
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
            return requests.get(url=url, headers=headers)
        except Exception as e:
            self.logger.error(f'Unexpected error occurred. Error details: {e}')
            return None

    def response_has_errors(self, response):
        return 'errors' in response or 'data' not in response

    def collect_response_errors(self, response):
        if 'errors' in response:
            for err in response['errors']:
                self.errors.append(err['detail'])
        elif 'data' not in response:
            self.errors.append(response['detail'])

    def find_twitter_user_id_by_username(self, username):
        response = self.do_request(f'{self.config.base_url}/users/by/username/{username}?user.fields=id')
        if response is None:
            return None

        twitter_user_data = response.json()
        if self.response_has_errors(twitter_user_data):
            self.collect_response_errors(twitter_user_data)
            return None

        return int(twitter_user_data['data']['id'])

    def find_twitter_following_by_user_id(self, user_id, user_fields='name,username,description'):
        response = self.do_request(
            f'{self.config.base_url}/users/{user_id}/following?max_results={self.config.max_results}&user.fields={user_fields}')
        if response is None:
            return None

        twitter_user_data = response.json()
        if self.response_has_errors(twitter_user_data):
            self.collect_response_errors(twitter_user_data)
            return None

        return twitter_user_data['data']
