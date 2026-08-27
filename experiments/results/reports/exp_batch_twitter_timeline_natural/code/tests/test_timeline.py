from twitter import Tweet, User, Twitter


def make_user(tw: Twitter, name: str) -> User:
    return tw.create_user(name)


def test_post_and_own_timeline():
    tw = Twitter()
    u = tw.create_user("alice")
    tw.post_tweet(u.user_id, "hello world")
    tw.post_tweet(u.user_id, "second tweet")
    timeline = tw.get_timeline(u.user_id)
    assert [t.text for t in timeline] == ["second tweet", "hello world"]


def test_follow_fanout_on_write():
    tw = Twitter()
    alice = tw.create_user("alice")
    bob = tw.create_user("bob")
    tw.follow(bob.user_id, alice.user_id)
    tw.post_tweet(alice.user_id, "alice says hi")
    assert [t.text for t in tw.get_timeline(bob.user_id)] == ["alice says hi"]


def test_unfollow_stops_new_delivery():
    tw = Twitter()
    alice = tw.create_user("alice")
    bob = tw.create_user("bob")
    tw.follow(bob.user_id, alice.user_id)
    tw.post_tweet(alice.user_id, "before unfollow")
    tw.unfollow(bob.user_id, alice.user_id)
    tw.post_tweet(alice.user_id, "after unfollow")
    texts = [t.text for t in tw.get_timeline(bob.user_id)]
    assert "before unfollow" in texts
    assert "after unfollow" not in texts


def test_timeline_reverse_chronological_across_users():
    tw = Twitter()
    alice = tw.create_user("alice")
    bob = tw.create_user("bob")
    carol = tw.create_user("carol")
    tw.follow(carol.user_id, alice.user_id)
    tw.follow(carol.user_id, bob.user_id)
    tw.post_tweet(alice.user_id, "a1")
    tw.post_tweet(bob.user_id, "b1")
    tw.post_tweet(alice.user_id, "a2")
    assert [t.text for t in tw.get_timeline(carol.user_id)] == ["a2", "b1", "a1"]


def test_celebrity_fanout_on_read():
    tw = Twitter(celebrity_threshold=3)
    celeb = tw.create_user("celebrity")
    followers = [tw.create_user(f"fan{i}") for i in range(3)]
    for fan in followers:
        tw.follow(fan.user_id, celeb.user_id)
    tw.post_tweet(celeb.user_id, "celebrity broadcast")
    for fan in followers:
        assert [t.text for t in tw.get_timeline(fan.user_id)] == ["celebrity broadcast"]


def test_celebrity_tweet_not_pushed_to_home_cache():
    tw = Twitter(celebrity_threshold=1)
    celeb = tw.create_user("celeb")
    fan = tw.create_user("fan")
    tw.follow(fan.user_id, celeb.user_id)
    tw.post_tweet(celeb.user_id, "broadcast")
    assert list(tw._home_timeline[fan.user_id]) == []
    assert [t.text for t in tw.get_timeline(fan.user_id)] == ["broadcast"]


def test_timeline_limit():
    tw = Twitter()
    u = tw.create_user("alice")
    for i in range(10):
        tw.post_tweet(u.user_id, f"tweet {i}")
    assert len(tw.get_timeline(u.user_id, limit=4)) == 4
