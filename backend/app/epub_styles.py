"""EPUB 的样式模板。

**模板是代码常量，不是作者数据。** 与参数档同一条先例：产品定义的东西不该进
数据库 —— 进去就要迁移、要快照、要在快照回滚时被回滚。作者每次导出时选一个。

样式只写进口袋里的 `style.css`，**不内联到每章**：内联会让改一处样式要改 N 个
文件，体积也翻倍。
"""

from __future__ import annotations

TEMPLATES: dict[str, str] = {
    "plain": "素雅",
    "classic": "传统",
}

DEFAULT_TEMPLATE = "plain"

_PLAIN = """\
/* 素雅：无衬线，段间留白，不缩进。适合屏幕阅读与轻小说。 */
body {
  font-family: "Source Han Sans SC", "Noto Sans CJK SC", "Microsoft YaHei", sans-serif;
  line-height: 1.75;
  margin: 0 1.2em;
  color: #1a1a1a;
}
h2.chapter-title {
  font-size: 1.4em;
  font-weight: 600;
  text-align: center;
  margin: 2em 0 1.6em;
  page-break-before: always;
}
h1.volume-title {
  font-size: 2em;
  font-weight: 600;
  text-align: center;
  margin: 40% 0 0;
  page-break-before: always;
}
p {
  margin: 0 0 0.9em;
  text-indent: 0;
}
blockquote {
  margin: 0.9em 1.5em;
  color: #555;
}
hr {
  border: none;
  border-top: 1px solid #ccc;
  margin: 1.8em 2em;
}
/* 封面页整页铺图，不能被正文的页边距框住。 */
body.cover-page {
  margin: 0;
  padding: 0;
}
.cover {
  margin: 0;
  padding: 0;
  text-align: center;
}
.cover img {
  max-width: 100%;
  max-height: 100%;
}
"""

_CLASSIC = """\
/* 传统：衬线，首行缩进两字，章首不缩进。适合长篇小说的纸书读感。 */
body {
  font-family: "Source Han Serif SC", "Noto Serif CJK SC", "SimSun", serif;
  line-height: 1.85;
  margin: 0 1.2em;
  color: #111;
}
h2.chapter-title {
  font-size: 1.35em;
  font-weight: 600;
  text-align: center;
  margin: 2.2em 0 1.8em;
  page-break-before: always;
}
h1.volume-title {
  font-size: 2.2em;
  font-weight: 600;
  text-align: center;
  margin: 40% 0 0;
  page-break-before: always;
}
p {
  margin: 0;
  text-indent: 2em;
}
/* 章题后的第一段不缩进 —— 纸书的通例。 */
h2.chapter-title + p {
  text-indent: 0;
}
blockquote {
  margin: 0.9em 1.5em;
  color: #555;
  text-indent: 0;
}
hr {
  border: none;
  border-top: 1px solid #bbb;
  margin: 1.8em 2em;
}
/* 封面页整页铺图，不能被正文的页边距框住。 */
body.cover-page {
  margin: 0;
  padding: 0;
}
.cover {
  margin: 0;
  padding: 0;
  text-align: center;
}
.cover img {
  max-width: 100%;
  max-height: 100%;
}
"""

_CSS = {
    "plain": _PLAIN,
    "classic": _CLASSIC,
}


def normalize_template(value: str | None) -> str:
    """接受 key，也接受中文标签；空值给默认模板。"""
    text = value.strip() if isinstance(value, str) else ""
    if not text:
        return DEFAULT_TEMPLATE
    if text in _CSS:
        return text
    for key, label in TEMPLATES.items():
        if label == text:
            return key
    raise ValueError(
        f"未知的 EPUB 样式模板「{value}」，可用值：{' / '.join(TEMPLATES)}"
    )


def template_css(key: str) -> str:
    try:
        return _CSS[key]
    except KeyError as exc:
        raise ValueError(
            f"未知的 EPUB 样式模板「{key}」，可用值：{' / '.join(TEMPLATES)}"
        ) from exc
