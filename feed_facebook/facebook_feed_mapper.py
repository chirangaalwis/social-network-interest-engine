import facebook
import os
import requests
import sys

try:
    sys.path.insert(0, os.path.realpath(os.environ['INTEREST_ENGINE_PATH']))
except KeyError:
    sys.stderr.write("Application Root environmental variable 'INTEREST_ENGINE_PATH' not set\n")
    sys.exit(1)
from feed_facebook.utils import convert_community_posts_to_native_statuses, convert_posts_to_native_statuses, get_status_index
from social_networks.concepts import SocialNetworkFeed, SocialNetworkMember
from social_networks.utils import load_latest_status_ids, update_latest_status_ids


class FacebookFeedMapper(SocialNetworkFeed):
    def __init__(self, token):
        self.graph = facebook.GraphAPI(token)
        self.user_id = (self.graph.request(self.graph.version + '/me', 'access_token=' + self.graph.access_token))['id']

    def get_public_trends_feed(self, **coordinates):
        pass

    def get_user_timeline_feed(self):
        # Capture the optional id value of the Facebook status since which posts are to be returned
        last_id = None
        ids = load_latest_status_ids()
        if 'facebook_user_timeline' in ids:
            last_id = ids['facebook_user_timeline']

        posts = self.graph.get_connections('me', 'posts',
                                           fields='id,description,updated_time,message,message_tags,name,parent_id')
        if last_id is None:
            statuses = convert_posts_to_native_statuses(posts['data'], self.graph)
            while len(statuses) < 150:
                try:
                    posts = requests.get(posts['paging']['next']).json()
                    statuses.extend(convert_posts_to_native_statuses(posts['data'], self.graph))
                except KeyError:
                    break
        else:
            statuses = convert_posts_to_native_statuses(posts['data'], self.graph)

            index = get_status_index(statuses, last_id)
            while index is None:
                try:
                    posts = requests.get(posts['paging']['next']).json()
                    statuses.extend(convert_posts_to_native_statuses(posts['data'], self.graph))

                    index = get_status_index(statuses, last_id)
                except KeyError:
                    break

            statuses = statuses[:index]

        if len(statuses) > 0:
            update_latest_status_ids('facebook_user_timeline', statuses[0].id)

        return statuses

    def get_bookmarks_feed(self):
        pass

    def get_followings_feed(self):
        likes = self.graph.get_connections('me', 'likes')

        followings_feed = []
        if 'data' in likes:
            for like in likes['data']:
                response = self.graph.get_connections(like['id'], 'feed',
                                                      fields='id,description,updated_time,message,message_tags,name,'
                                                             'parent_id')

                posts = convert_posts_to_native_statuses(response['data'], self.graph)

                index = 0
                while index < len(posts):
                    posts[index].text = like['name'] + ':' + posts[index].text
                    index += 1

                followings_feed.extend(posts)

        return followings_feed

    def get_community_feed(self):
        content = self.graph.get_connections('me', 'groups')
        groups = content['data']
        username = self.graph.get_object('me')['name']

        while True:
            try:
                more = requests.get(content['paging']['next']).json()
                groups.extend(more['data'])
            except KeyError:
                break

        group_members = []
        for group in groups:
            feed = self.graph.get_connections(group['id'], 'feed',
                                              fields='id,description,updated_time,'
                                                     'story,message,message_tags,name,parent_id')
            group_feed = feed['data']
            count = 0
            while len(group_feed) < 30:
                try:
                    more = requests.get(feed['paging']['next']).json()
                    group_feed.extend(more['data'])

                    if count == len(group_feed):
                        break
                    count = len(group_feed)
                except KeyError:
                    break

            filtered = [item for item in group_feed if 'story' in item]
            filtered = [item for item in filtered if item['story'].startswith(username) is False]
            statuses = convert_community_posts_to_native_statuses(filtered, self.graph)

            members = self.graph.get_connections(group['id'], 'members')['data']
            for member in members:
                member_username = member['name']
                member_statuses = [status for status in statuses if member_username in status[1]]

                member_content = ''
                for status in member_statuses:
                    member_content += (status[0].text + ' ')
                member_content = member_content.strip()

                group_members.append(SocialNetworkMember(identifier=member['id'], content=member_content))

        return [member for member in group_members if member.content]


if __name__ == '__main__':
    obj = FacebookFeedMapper(os.environ.get('FACEBOOK_ACCESS_TOKEN'))

    # for post in obj.get_user_timeline_feed():
    #     print(post.text)
    #     print(post.score)
    #     print()

    # for status in obj.get_followings_feed():
    #     print(status.text)

    for member in obj.get_community_feed():
        print(member.id)
        print(member.content)
