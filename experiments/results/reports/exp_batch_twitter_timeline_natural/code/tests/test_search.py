from twitter import Twitter


def test_search_single_term():
    tw = Twitter()
    u = tw.create_user("alice")
    tw.post_tweet(u.user_id, "the quick brown fox")
    tw.post_tweet(u.user_id, "a lazy dog")
    results = tw.search("brown")
    assert [t.text for t in results] == ["the quick brown fox"]


def test_search_multi_term_and():
    tw = Twitter()
    u = tw.create_user("alice")
    tw.post_tweet(u.user_id, "hello world")
    tw.post_tweet(u.user_id, "hello moon")
    tw.post_tweet(u.user_id, "goodbye world")
    results = tw.search("hello world")
    assert [t.text for t in results] == ["hello world"]


def test_search_no_results():
    tw = Twitter()
    u = tw.create_user("alice")
    tw.post_tweet(u.user_id, "hello")
    assert tw.search("zzz") == []
    assert tw.search("hello zzz") == []


def test_search_ordered_newest_first():
    tw = Twitter()
    u = tw.create_user("alice")
    tw.post_tweet(u.user_id, "weather is nice")
    tw.post_tweet(u.user_id, "weather again")
    results = tw.search("weather")
    assert [t.text for t in results] == ["weather again", "weather is nice"]


def test_hashtag_search():
    tw = Twitter()
    u = tw.create_user("alice")
    tw.post_tweet(u.user_id, "I love #python")
    tw.post_tweet(u.user_id, "no hashtag here")
    assert [t.text for t in tw.search("#python")] == ["I love #python"]
    assert [t.text for t in tw.search("python")] == ["I love #python"]


def test_mention_search():
    tw = Twitter()
    u = tw.create_user("alice")
    tw.post_tweet(u.user_id, "hey @bob what's up")
    tw.post_tweet(u.user_id, "nothing to see")
    assert [t.text for t in tw.search("@bob")] == ["hey @bob what's up"]


def test_search_is_case_insensitive():
    tw = Twitter()
    u = tw.create_user("alice")
    tw.post_tweet(u.user_id, "Hello World")
    assert [t.text for t in tw.search("hello")] == ["Hello World"]
