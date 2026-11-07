from nataware.voice.chunker import SpeechChunker, split_sentences


def feed_all(chunker, deltas):
    out = []
    for d in deltas:
        out += chunker.feed(d)
    return out + chunker.flush()


def test_emits_only_complete_sentences():
    c = SpeechChunker()
    assert c.feed("Hello there") == []
    assert c.feed(". How are") == ["Hello there."]
    assert c.flush() == ["How are"]


def test_decimal_amounts_do_not_split():
    assert split_sentences("You spent £12.99 on Netflix. Nice.") == ["You spent £12.99 on Netflix.", "Nice."]


def test_profile_block_is_never_spoken_even_when_tag_is_split():
    deltas = ["Great chat. You're a Scrapper.", " <pro", "file>{\"capacity\": ", "\"The Scrapper\"}</profile>"]
    spoken = feed_all(SpeechChunker(), deltas)
    assert spoken == ["Great chat.", "You're a Scrapper."]
    assert not any("profile" in s or "{" in s for s in spoken)


def test_partial_tag_at_end_of_stream_is_dropped():
    assert feed_all(SpeechChunker(), ["All done. <prof"]) == ["All done."]


def test_lone_angle_bracket_text_still_flows():
    assert feed_all(SpeechChunker(), ["3 < 5 is true. ", "Yes."]) == ["3 < 5 is true.", "Yes."]
