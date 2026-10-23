"""P5a 走查：整本正文接口。临时目录，不调用模型。"""

import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8756"
results: list[tuple[str, bool, str]] = []


def call(method: str, path: str, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"content-type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req) as response:
            raw = response.read()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, (json.loads(raw) if raw else None)


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))


def text(path: str) -> str:
    with urllib.request.urlopen(BASE + path) as response:
        return response.read().decode("utf-8")


# ---- 骨架：两卷三章，其中一章无正文 ----
project = call("POST", "/api/projects", {"name": "P5a 走查"})[1]
pid = project["id"]
v1 = call("POST", f"/api/projects/{pid}/volumes", {"name": "第一卷"})[1]
v2 = call("POST", f"/api/projects/{pid}/volumes", {"name": "第二卷"})[1]
c1 = call("POST", f"/api/volumes/{v1['id']}/chapters", {"title": "开端"})[1]
c2 = call("POST", f"/api/volumes/{v1['id']}/chapters", {"title": "空章"})[1]
c3 = call("POST", f"/api/volumes/{v2['id']}/chapters", {"title": "转折"})[1]

s1 = call("POST", f"/api/chapters/{c1['id']}/scenes", {"goal": "开场"})[1]
s2 = call("POST", f"/api/chapters/{c1['id']}/scenes", {"goal": "推进"})[1]
s3 = call("POST", f"/api/chapters/{c3['id']}/scenes", {"goal": "转折"})[1]
call("PUT", f"/api/scenes/{s1['id']}/body", {"content": "# 开场\n\n雨落在旧城。\n\n> 他记得。"})
call("PUT", f"/api/scenes/{s2['id']}/body", {"content": "灯亮着，**没有人**。"})
call("PUT", f"/api/scenes/{s3['id']}/body", {"content": "他推开门。"})

# ---- 1. 整本一次取回 ----
status, book = call("GET", f"/api/projects/{pid}/book")
check("整本接口 200", status == 200, str(status))
titles = [ch["title"] for vol in book["volumes"] for ch in vol["chapters"]]
check(
    "空章也列出来（作者要看得到还差哪几章）",
    titles == ["开端", "空章", "转折"],
    str(titles),
)
check(
    "空章标 has_body=False 且正文为空",
    next(ch for vol in book["volumes"] for ch in vol["chapters"] if ch["title"] == "空章")[
        "has_body"
    ]
    is False,
    str(titles),
)
check(
    "写完章数与总章数",
    book["written_chapters"] == 2 and book["total_chapters"] == 3,
    f"{book['written_chapters']}/{book['total_chapters']}",
)

# ---- 2. 章内正文按场景顺序拼接 ----
first = book["volumes"][0]["chapters"][0]
check(
    "章内多个场景按顺序拼接",
    first["content"].index("雨落在旧城") < first["content"].index("灯亮着"),
    first["content"][:60],
)
check("Markdown 原文原样返回", "**没有人**" in first["content"], first["content"][:80])

# ---- 3. 字数 ----
total = sum(ch["word_count"] for vol in book["volumes"] for ch in vol["chapters"])
check("总字数等于各章之和", book["total_words"] == total, f"{book['total_words']} vs {total}")
check("章字数非零", first["word_count"] > 0, str(first["word_count"]))

# ---- 4. 与导出逐字一致 ----
markdown = text(f"/api/projects/{pid}/export?format=md")
check(
    "阅读器拿到的内容与 Markdown 导出一致",
    first["content"] in markdown,
    first["content"][:60],
)
plain = text(f"/api/projects/{pid}/export?format=txt")
check("TXT 导出含同一段正文", "雨落在旧城" in plain.replace("\n", ""), plain[:60])

# ---- 5. 空项目与不存在的项目 ----
empty = call("POST", "/api/projects", {"name": "空书"})[1]
status, empty_book = call("GET", f"/api/projects/{empty['id']}/book")
check(
    "空项目返回空卷列表而不是报错",
    status == 200 and empty_book["volumes"] == [] and empty_book["total_words"] == 0,
    json.dumps(empty_book, ensure_ascii=False)[:80],
)
check("不存在的项目 404", call("GET", "/api/projects/nope/book")[0] == 404)

# ---- 6. 未写的章不进正文，但仍出现在树里 ----
s4 = call("POST", f"/api/chapters/{c2['id']}/scenes", {"goal": "空场"})[1]
status, book2 = call("GET", f"/api/projects/{pid}/book")
blank = next(
    ch for vol in book2["volumes"] for ch in vol["chapters"] if ch["title"] == "空章"
)
check(
    "未写的章 has_body=False、正文为空、字数为 0",
    blank["has_body"] is False and blank["content"] == "" and blank["word_count"] == 0,
    str(s4["id"][:8]),
)
check(
    "空章的正文不出现在导出里",
    "空章" not in text(f"/api/projects/{pid}/export?format=md"),
    "export contains 空章",
)

failed = [row for row in results if not row[1]]
for name, ok, detail in results:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  → {detail}"))
print(f"\n{len(results) - len(failed)}/{len(results)} 通过")
