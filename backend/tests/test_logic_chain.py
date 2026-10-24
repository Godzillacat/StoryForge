"""逻辑链：三类连接词、多类型取第一个、不硬凑。"""

from app.logic_chain import extract_chain, summarize


def test_a_cause_sentence_is_extracted_with_its_paragraph():
    text = "雨停了。\n\n因为他听见了脚步声，所以他停下了。"

    chain = extract_chain(text)

    assert len(chain) == 1
    assert chain[0]["paragraph"] == 2
    assert chain[0]["kind"] == "cause"
    assert "因为" in chain[0]["marker"]


def test_a_turn_sentence_is_extracted():
    chain = extract_chain("他以为安全了。但是门外有人。")

    assert [item["kind"] for item in chain] == ["turn"]
    assert chain[0]["marker"] == "但是"


def test_a_reveal_sentence_is_extracted():
    chain = extract_chain("他推开门。原来屋里一直有人。")

    assert [item["kind"] for item in chain] == ["reveal"]


def test_a_sentence_with_several_markers_takes_the_first_kind():
    """「因为…但是…」里作者真正推进的是因果。"""
    chain = extract_chain("因为他迟到了，但是没人发现。")

    assert chain[0]["kind"] == "cause"


def test_sentences_without_markers_are_not_forced_in():
    chain = extract_chain("雨停了。他走出门。天很蓝。")

    assert chain == []


def test_paragraphs_are_numbered_from_one_and_blank_ones_are_skipped():
    """作者数的是他看得见的段，空行不占位。"""
    text = "第一段没有。\n\n\n\n所以这一段有。\n\n第三段没有。"

    chain = extract_chain(text)

    assert chain[0]["paragraph"] == 2


def test_an_empty_body_yields_an_empty_chain():
    assert extract_chain(None) == []
    assert extract_chain("") == []
    assert extract_chain("   ") == []


def test_the_chain_keeps_the_original_order():
    text = "因为下雨。所以路滑。但是他没有停。"

    kinds = [item["kind"] for item in extract_chain(text)]

    assert kinds == ["cause", "cause", "turn"]


def test_summarize_counts_by_kind():
    chain = extract_chain("因为下雨。但是他没有停。原来他在等人。")

    assert summarize(chain) == {"total": 3, "cause": 1, "turn": 1, "reveal": 1}


def test_the_first_occurring_marker_is_reported():
    """「于是…因为…」里先出现的是「于是」，报它；类型仍是因果。"""
    chain = extract_chain("于是他停下，因为下雨。")

    assert chain[0]["kind"] == "cause"
    assert chain[0]["marker"] == "于是"


def test_count_paragraphs_ignores_blank_runs():
    from app.logic_chain import count_paragraphs

    assert count_paragraphs("第一段。\n\n\n第二段。\n\n   \n第三段。") == 3
    assert count_paragraphs("") == 0
    assert count_paragraphs(None) == 0


def test_count_paragraphs_agrees_with_extract_chain():
    from app.logic_chain import count_paragraphs, extract_chain

    text = "开头。\n\n因为下雨，他留下。\n\n\n结尾。"
    chain = extract_chain(text)
    assert count_paragraphs(text) == 3
    assert max(item["paragraph"] for item in chain) <= count_paragraphs(text)
