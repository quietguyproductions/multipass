from typing import *
import hashlib
from datetime import datetime
import feedgenerator
from abc import ABC, abstractmethod
import tweepy
from mastodon import Mastodon
import praw
import facebook
import InstagramAPI
import google.auth
from googleapiclient.discovery import build


class Platform(ABC):
    """
    Abstract class for interacting with various social media platforms.
    """
    def __init__(self):
        self.authenticated = False

    @abstractmethod
    def authenticate(self):
        raise NotImplementedError()

    @abstractmethod
    def post(self, post: SocialMediaPost):
        raise NotImplementedError()

    @abstractmethod
    def get_posts(self, filters: dict = {}):
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def get_platform_name(cls):
        raise NotImplementedError()

    @classmethod
    def get_all(cls):
        return [Twitter(), Mastodon(), Facebook(), Reddit(), Youtube(), Instagram()]


class Twitter(Platform):
    def __init__(self):
        super().__init__()
        self.api = None

    def authenticate(self, access_token: str, access_token_secret: str, consumer_key: str, consumer_secret: str):
        auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
        auth.set_access_token(access_token, access_token_secret)
        self.api = tweepy.API(auth)
        self.authenticated = True

    def post(self, post: SocialMediaPost):
        if not self.authenticated:
            raise Exception("Not authenticated.")
        self.api.update_status(post.content)

    def get_posts(self, filters: dict = {}):
        if not self.authenticated:
            raise Exception("Not authenticated.")
        statuses = self.api.home_timeline()
        return [SocialMediaPost(post.created_at, post.text, self) for post in statuses]

    @classmethod
    def get_platform_name(cls):
        return "Twitter"


class Mastodon(Platform):
    def __init__(self):
        super().__init__()
        self.api = None

    def authenticate(self, access_token: str, base_url: str):
        self.api = Mastodon(
            access_token=access_token,
            api_base_url=base_url
        )
        self.authenticated = True

    def post(self, post: SocialMediaPost):
        if not self.authenticated:
            raise Exception("Not authenticated.")
        self.api.status_post(post.content, visibility='public')

    def get_posts(self, filters: dict = {}):
        if not self.authenticated:
            raise Exception("Not authenticated.")
        statuses = self.api.timeline_home()
        return [SocialMediaPost(post['created_at'], post['content'], self) for post in statuses]

    @classmethod
    def get_platform_name(cls):
        return "Mastodon"


class Reddit(Platform):
    def __init__(self):
        super().__init__()
        self.api = None

    def authenticate(self, client_id: str, client_secret: str, username: str, password: str):
        self.api = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            username=username,
            password=password,
            user_agent='MultiPass/0.0.1'
        )
        self.authenticated = True

    def post(self, post: SocialMediaPost):
        if not self.authenticated:
            raise Exception("Not authenticated.")
        self.api.subreddit("all").submit(title=post.content, selftext="")

    def get_posts(self, filters: dict = {}):
        if not self.authenticated:
            raise Exception("Not authenticated.")
        posts = self.api.subreddit("all").new(limit=100)
        return [SocialMediaPost(post.created_utc, post.title, self) for post in posts]

    @classmethod
    def get_platform_name(cls):
        return "Reddit"


class Facebook(Platform):
    def __init__(self):
        super().__init__()
        self.api = None

    def authenticate(self, access_token: str):
        self.api = facebook.GraphAPI(access_token=access_token)
        self.authenticated = True

    def post(self, post: SocialMediaPost):
        if not self.authenticated:
            raise Exception("Not authenticated.")
        self.api.put_object(parent_object="me", connection_name="feed", message=post.content)

    def get_posts(self, filters: dict = {}):
        if not self.authenticated:
            raise Exception("Not authenticated.")
        posts = self.api.get_connections("me", "feed")
        return [SocialMediaPost(post["created_time"], post["message"], self) for post in posts["data"]]

    @classmethod
    def get_platform_name(cls):
        return "Facebook"


class Instagram(Platform):
    def __init__(self):
        super().__init__()
        self.api = None

    def authenticate(self, username: str, password: str):
        self.api = InstagramAPI.InstagramAPI(username, password)
        self.api.login()
        self.authenticated = True

    def post(self, post: SocialMediaPost):
        if not self.authenticated:
            raise Exception("Not authenticated.")
        self.api.uploadPhoto(post.content, None, None)

    def get_posts(self, filters: dict = {}):
        if not self.authenticated:
            raise Exception("Not authenticated.")
        self.api.getSelfUserFeed()
        recent_posts = self.api.LastJson
        return [SocialMediaPost(post["taken_at_timestamp"], post["edge_media_to_caption"]["edges"][0]["node"]["text"], self) for post in recent_posts["feed"]["edge"]]

    @classmethod
    def get_platform_name(cls):
        return "Instagram"


class YouTube(Platform):
    def __init__(self):
        super().__init__()
        self.youtube = None
        self.channel_id = None

    def authenticate(self, client_id: str, client_secret: str, refresh_token: str):
        # Use OAuth2 to authenticate with YouTube API
        credentials = google.oauth2.credentials.Credentials.from_authorized_user_info(info={"client_id": client_id, "client_secret": client_secret, "refresh_token": refresh_token})
        self.youtube = build('youtube', 'v3', credentials=credentials)
        self.authenticated = True

        # Get the authenticated user's channel
        request = self.youtube.channels().list(part='id', mine=True)
        response = request.execute()
        self.channel_id = response['items'][0]['id']

    def post(self, post: SocialMediaPost):
        if not self.authenticated:
            raise Exception("Not authenticated.")
        video_file = post.content

        request = self.youtube.videos().insert(
            part='snippet,status',
            body={
                'snippet': {
                    'title': post.title,
                    'description': post.body,
                    'categoryId': 22
                },
                'status': {
                    'privacyStatus': 'private'
                }
            },
            media_body=video_file
        )
        response = request.execute()
        print(response)

    def get_posts(self, filters: dict = {}):
        if not self.authenticated:
            raise Exception("Not authenticated.")
        request = self.youtube.search().list(
            part='snippet',
            channelId=self.channel_id,
            type='video',
            order='date'
        )
        response = request.execute()
        posts = []
        for video in response['items']:
            timestamp = video['snippet']['publishedAt']
            title = video['snippet']['title']
            body = video['snippet']['description']
            post = SocialMediaPost(timestamp, title, body, self)
            posts.append(post)
        return posts

    @classmethod
    def get_platform_name(cls):
        return "YouTube"


class SocialMediaPost:
    def __init__(self, platform: Platform, post_id: str, 
                 content: str, timestamp: int,
                 metadata: Optional[Dict] = None):
        self.platform = platform
        self.post_id = post_id
        self.content = content
        self.timestamp = timestamp
        self.metadata = metadata

    def to_rss_item(self):
        item = {}
        item["title"] = self.content
        item["link"] = self.platform.get_post_url(self.post_id)
        item["description"] = self.content
        item["guid"] = self.post_id
        item["pubDate"] = self.timestamp
        item.update(self.metadata)
        return item


class CustomFilter:
    def __init__(self, platform: Type[Platform], condition: Optional[callable] = None):
        self.platform = platform
        self.condition = condition

    def __call__(self, post: SocialMediaPost):
        return isinstance(post.platform, self.platform) and (
            not self.condition or self.condition(post)
        )


class Multipass:
    def __init__(self, platforms: List[Type[Platform]], filters: Optional[List[CustomFilter]] = None):
        self.platforms = platforms
        self.filters = filters or []
        self.posts = []
        self.post_ids = set()

    def filter_posts(self, posts: List[SocialMediaPost]) -> List[SocialMediaPost]:
        filtered_posts = [post for post in posts if all(f(post) for f in self.filters)]
        return filtered_posts

    def aggregate_posts(self):
        for platform in self.platforms:
            platform_posts = platform.get_posts()
            for post in platform_posts:
                if post.post_id not in self.post_ids:
                    self.posts.append(post)
                    self.post_ids.add(post.post_id)

    def get_posts(self) -> List[SocialMediaPost]:
        self.aggregate_posts()
        self.posts.sort(key=lambda x: x.timestamp, reverse=True)
        return self.posts

    def multi_post(self, content: str, metadata: Optional[Dict] = None):
        for platform in self.platforms:
            platform.post(content, metadata)

    def multi_feed(self, filter_platform: Optional[str] = None) -> List[Dict]:
        self.aggregate_posts()
        posts = self.posts
        if filter_platform:
            posts = [post for post in self.posts if post.platform.name == filter_platform]
        feed = [post.to_rss_item() for post in posts]
        return feed


from fastapi import FastAPI, HTTPException
from typing import List

app = FastAPI()

@app.post("/create_multipass")
async def create_multipass(platforms: List[Platform]):
    """
    Create a new Multipass instance with the given platforms.
    """
    multipass = Multipass(platforms)
    return {"message": "Multipass created"}

@app.get("/posts")
async def get_posts(multipass: Multipass):
    """
    Get a unified and deduplicated feed of posts from all platforms in the Multipass.
    """
    posts = multipass.get_posts()
    if not posts:
        raise HTTPException(status_code=204, detail="No posts found")
    return posts

@app.post("/post")
async def post_message(multipass: Multipass, message: str):
    """
    Post a message on all platforms in the Multipass.
    """
    multipass.post(message)
    return {"message": "Post successful"}

@app.get("/filter_posts")
async def filter_posts(multipass: Multipass, platform: str):
    """
    Filter posts in the unified feed based on the platform they came from.
    """
    posts = multipass.filter_posts(platform)
    if not posts:
        raise HTTPException(status_code=204, detail="No posts found")
    return posts

