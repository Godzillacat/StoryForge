"""EPUB 样式模板：两套都是代码常量，未知 key 报错。"""

import pytest

from app import epub_styles


def test_both_templates_are_non_empty_and_distinct():
    plain = epub_styles.template_css("plain")
    classic = epub_styles.template_css("classic")

    assert plain.strip() and classic.strip()
    assert plain != classic


def test_classic_indents_paragraphs_and_plain_does_not():
    assert "text-indent: 2em" in epub_styles.template_css("classic")
    assert "text-indent: 0" in epub_styles.template_css("plain")


def test_both_templates_keep_chapter_titles_and_page_breaks():
    for key in epub_styles.TEMPLATES:
        css = epub_styles.template_css(key)
        assert "h2.chapter-title" in css
        assert "page-break-before: always" in css


def test_normalize_accepts_keys_labels_and_blank():
    assert epub_styles.normalize_template("classic") == "classic"
    assert epub_styles.normalize_template("传统") == "classic"
    assert epub_styles.normalize_template("") == epub_styles.DEFAULT_TEMPLATE
    assert epub_styles.normalize_template(None) == epub_styles.DEFAULT_TEMPLATE


def test_unknown_template_is_rejected():
    with pytest.raises(ValueError, match="未知的 EPUB 样式模板"):
        epub_styles.normalize_template("fancy")
    with pytest.raises(ValueError, match="未知的 EPUB 样式模板"):
        epub_styles.template_css("fancy")
