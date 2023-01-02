from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from twitter_api import TwitterApiConfig, TwitterApi
from mastodon_api import MastodonApiConfig, MastodonApi
from datetime import datetime
import time
import json
import re

app = Flask(__name__)
app.config.from_file('config.json', load=json.load)

db = SQLAlchemy(app)


class SearchCache(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    t_username = db.Column(db.String())
    created = db.Column(db.DateTime(), default=datetime.now)
    updated = db.Column(db.DateTime(), default=datetime.now)
    # [info] Create relations
    results = db.relationship('ResultCache', backref='search_cache')


class ResultCache(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    search_id = db.Column(db.Integer, db.ForeignKey(SearchCache.id))
    t_username = db.Column(db.String())
    t_name = db.Column(db.String())
    t_description = db.Column(db.String())
    m_username = db.Column(db.String())
    m_name = db.Column(db.String())
    m_description = db.Column(db.String())
    created = db.Column(db.DateTime(), default=datetime.now)
    updated = db.Column(db.DateTime(), default=datetime.now)


def create_twitter_api_config():
    config = {
        'base_url': app.config['TWITTER_API_URL'],
        'auth_token': app.config['TWITTER_API_TOKEN'],
        'max_results': app.config['TWITTER_API_MAX_RESULTS'],
    }

    return TwitterApiConfig(config)


def create_mastodon_api_config():
    config = {
        'base_url': app.config['MASTODON_API_URL'],
        'auth_token': app.config['MASTODON_API_TOKEN'],
    }

    return MastodonApiConfig(config)


def extract_mastodon_handle(text):
    """
    Mastodon handle format: @<username>@<mastodon-server>
    Ex: @cristianradulescu@phpc.social
    """
    # [info] Use Regex
    mastodon_handle = re.findall("(@\w+@[a-zA-Z0-9]+[a-zA-Z0-9-._]*[a-zA-Z0-9]+)", text)
    if len(mastodon_handle) > 0:
        return mastodon_handle[0]

    return None


def do_search_request(username):
    results = []
    twitter_api_client = TwitterApi(create_twitter_api_config(), logger=app.logger)
    twitter_user_id = twitter_api_client.find_twitter_user_id_by_username(username)
    if twitter_user_id is None:
        app.logger.warning(f'Username {username} not found!')
        return render_template('includes/search_result.html.jinja',
                               results=results,
                               errors=['Username not found!'])

    app.logger.debug(f'Found username {username} with id {twitter_user_id}')
    following_users_data = twitter_api_client.find_twitter_following_by_user_id(twitter_user_id)
    for users_data in following_users_data:
        # Users put the Mastodon handle in the account's description or name
        description = users_data['description']
        mastodon_handle = extract_mastodon_handle(description)
        if mastodon_handle is not None:
            users_data['mastodon'] = mastodon_handle
            results.append({
                't_username': users_data['username'],
                't_name': users_data['name'],
                't_description': users_data['description'],
                'm_username': users_data['mastodon'],
            }
            )
        else:
            name = users_data['name']
            mastodon_handle = extract_mastodon_handle(name)
            if mastodon_handle is not None:
                users_data['mastodon'] = mastodon_handle
                results.append({
                    't_username': users_data['username'],
                    't_name': users_data['name'],
                    't_description': users_data['description'],
                    'm_username': users_data['mastodon'],
                })

    return [results, twitter_api_client.errors]


@app.route('/')
def home():
    return render_template('home.html.jinja')


@app.route('/search', methods=['POST'])
def search():
    username = request.form['username']
    app.logger.debug(f'Searching for `{username}`')

    results = []
    errors = []
    using_cache = False
    cache_info = {}
    search_cache = SearchCache.query.filter_by(t_username=username).first()
    if search_cache is None:
        try:
            app.logger.debug('Username not found in search cache, will save it now.')
            search_cache = SearchCache(t_username=username)
            db.session.add(search_cache)
            db.session.commit()

            [results, errors] = do_search_request(username)
            mastodon_api_client = MastodonApi(create_mastodon_api_config(), logger=app.logger)

            for data in results:
                mastodon_user = mastodon_api_client.find_mastodon_user_by_username(data['m_username'])
                if mastodon_user is None:
                    continue

                data['m_name'] = mastodon_user['display_name']
                data['m_description'] = mastodon_user['note']
                result_cache = ResultCache(
                    search_id=search_cache.id,
                    t_username=data['t_username'],
                    t_name=data['t_name'],
                    t_description=data['t_description'],
                    m_username=data['m_username'],
                    m_name=data['m_name'],
                    m_description=data['m_description']
                )
                db.session.add(result_cache)
                time.sleep(2)
            db.session.commit()
        except Exception as e:
            app.logger.error(msg=f'Failed to cache search. {e}', exc_info=True)
    else:
        using_cache = True
        # [info] Date formatting
        cached_date = search_cache.updated
        cache_info[
            'date'] = f'{cached_date.year}-{cached_date.month}-{cached_date.day} {cached_date.hour}:{cached_date.minute}'
        # [info] Use relations
        cached_results = search_cache.results
        for cached_result in cached_results:
            results.append({
                't_username': cached_result.t_username,
                't_name': cached_result.t_name,
                't_description': cached_result.t_description,
                'm_username': cached_result.m_username,
                'm_name': cached_result.m_name,
                'm_description': cached_result.m_description
            })

    return render_template('includes/search_result.html.jinja', search=username, results=results, errors=errors,
                           using_cache=using_cache, cache_info=cache_info)


@app.route('/cache/delete')
def cache_delete():
    username = request.args.get('username')
    search_cache = SearchCache.query.filter_by(t_username=username).first()
    # [info] Bulk delete
    ResultCache.query.filter_by(search_id=search_cache.id).delete()
    SearchCache.query.filter_by(t_username=username).delete()
    db.session.commit()

    return redirect(url_for('home'))


if __name__ == '__main__':
    app.run(debug=True)
