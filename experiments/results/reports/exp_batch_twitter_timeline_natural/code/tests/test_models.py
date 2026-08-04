import pytest
from twitter import models


class TestUserModel:
    def test_create_user(self):
        user = models.User(id="u1", screen_name="alice")
        assert user.id == "u1"
        assert user.screen_name == "alice"
        assert user.follower_count == 0
        assert not user.is_celebrity()

    def test_celebrity_detection_with_default_threshold(self):
        user = models.User(id="u1", screen_name="celebrity")
        user.follower_count = 9999
        assert not user.is_celebrity()
        user.follower_count = 10000
        assert user.is_celebrity()
        user.follower_count = 10001
        assert user.is_celebrity()

    def test_celebrity_detection_with_custom_threshold(self):
        user = models.User(id="u1", screen_name="test")
        user.follower_count = 500
        assert not user.is_celebrity(threshold=1000)
        user.follower_count = 1000
        assert user.is_celebrity(threshold=1000)

    def test_user_created_at(self):
        user = models.User(id="u1", screen_name="alice")
        assert user.created_at > 0


class TestTweetModel:
    def test_create_tweet(self):
        tweet = models.Tweet(id="t1", user_id="u1", content="Hello World")
        assert tweet.id == "t1"
        assert tweet.user_id == "u1"
        assert tweet.content == "Hello World"
        assert tweet.created_at > 0

    def test_hashtags_extraction(self):
        tweet = models.Tweet(id="t1", user_id="u1", content="Hello #world this is #great")
        assert set(tweet.hashtags) == {"#world", "#great"}

    def test_hashtags_no_hashtags(self):
        tweet = models.Tweet(id="t1", user_id="u1", content="Hello World")
        assert tweet.hashtags == []

    def test_hashtags_edge_cases(self):
        tweet = models.Tweet(id="t1", user_id="u1", content="# #tag1 #tag2! #tag3.")
        assert set(tweet.hashtags) == {"#tag1", "#tag2", "#tag3"}


class TestFollowModel:
    def test_create_follow(self):
        follow = models.Follow(follower_id="u1", followee_id="u2")
        assert follow.follower_id == "u1"
        assert follow.followee_id == "u2"
        assert follow.created_at > 0

    def test_follow_equality(self):
        f1 = models.Follow(follower_id="u1", followee_id="u2")
        f2 = models.Follow(follower_id="u1", followee_id="u2")
        f3 = models.Follow(follower_id="u2", followee_id="u1")
        assert f1 == f2
        assert f1 != f3
        assert f1 != "not a follow"

    def test_follow_hash(self):
        f1 = models.Follow(follower_id="u1", followee_id="u2")
        f2 = models.Follow(follower_id="u1", followee_id="u2")
        assert hash(f1) == hash(f2)


class TestTimelineEntryModel:
    def test_create_timeline_entry(self):
        entry = models.TimelineEntry(
            user_id="u1",
            tweet_id="t1",
            author_id="u2",
            created_at=100.0,
        )
        assert entry.user_id == "u1"
        assert entry.tweet_id == "t1"
        assert entry.author_id == "u2"
        assert entry.created_at == 100.0

    def test_timeline_entry_ordering(self):
        e1 = models.TimelineEntry("u1", "t1", "u2", 100.0)
        e2 = models.TimelineEntry("u1", "t2", "u3", 200.0)
        e3 = models.TimelineEntry("u1", "t3", "u4", 50.0)
        entries = [e1, e2, e3]
        entries.sort()
        assert entries[0].created_at == 50.0
        assert entries[1].created_at == 100.0
        assert entries[2].created_at == 200.0


class TestTokenize:
    def test_tokenize_simple(self):
        tokens = models._tokenize("Hello World")
        assert tokens == ["hello", "world"]

    def test_tokenize_hashtags(self):
        tokens = models._tokenize("Hello #World #great_day")
        assert tokens == ["hello", "#world", "#great_day"]

    def test_tokenize_punctuation(self):
        tokens = models._tokenize("Hello, World! How are you?")
        assert tokens == ["hello", "world", "how", "are", "you"]

    def test_tokenize_empty(self):
        assert models._tokenize("") == []

    def test_tokenize_numbers(self):
        tokens = models._tokenize("test123 abc456")
        assert tokens == ["test123", "abc456"]
