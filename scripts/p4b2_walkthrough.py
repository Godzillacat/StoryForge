"""P4b-2 走查：开分支、保存、采纳、合并、丢弃、锁定。临时目录，不调用模型。"""

import json
import urllib.parse
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


project = call("POST", "/api/projects", {"name": "走查项目"})[1]
pid = project["id"]
volume = call("POST", f"/api/projects/{pid}/volumes", {"name": "第一卷"})[1]
chapter = call("POST", f"/api/volumes/{volume['id']}/chapters", {"title": "第一章"})[1]
scene = call("POST", f"/api/chapters/{chapter['id']}/scenes", {"goal": "转折点"})[1]
call("PUT", f"/api/scenes/{scene['id']}/body", {"content": "主版：他转身离开。"})

# 1. 开分支（从主版起步）
status, a = call("POST", f"/api/scenes/{scene['id']}/branches", {"name": "A 案"})
check(
    "开分支从主版正文起步",
    status == 201 and a["content"] == "主版：他转身离开。",
    f"{status} {a.get('content')}",
)
status, b = call("POST", f"/api/scenes/{scene['id']}/branches", {"name": "B 案"})
check("开第二条分支", status == 201, str(status))

# 2. 重名
check(
    "分支重名被拒",
    call("POST", f"/api/scenes/{scene['id']}/branches", {"name": "A 案"})[0] == 400,
)

# 3. 各写一版
call("PUT", f"/api/branches/{a['id']}/body", {"content": "A 案：他留下来。"})
call("PUT", f"/api/branches/{b['id']}/body", {"content": "B 案：他拔出了枪。"})
rows = call("GET", f"/api/scenes/{scene['id']}/branches")[1]
check(
    "两条分支各自有字数",
    len(rows) == 2 and all(row["chars"] > 0 for row in rows),
    str([(row["name"], row["chars"]) for row in rows]),
)
check(
    "分支正文不影响主版",
    call("GET", f"/api/scenes/{scene['id']}/text")[1]["body"] == "主版：他转身离开。",
)

# 4. 分支内采纳草稿
call("PUT", f"/api/branches/{b['id']}/draft", {"content": "B 案草稿：他拔枪，但没扣扳机。"})
status, adopted = call("POST", f"/api/branches/{b['id']}/adopt")
check(
    "分支内可采纳草稿",
    status == 200 and "没扣扳机" in adopted["content"] and adopted["draft"] is None,
    f"{status}",
)

# 5. 合并 A 案
status, merged = call("POST", f"/api/branches/{a['id']}/merge")
check(
    "合并后主版变成 A 案",
    status == 200 and merged["body"] == "A 案：他留下来。",
    f"{status} {merged.get('body')}",
)
text = call("GET", f"/api/scenes/{scene['id']}/text")[1]
check(
    "旧主版进了修订历史（来源 branch）",
    text["body"] == "A 案：他留下来。"
    and text["revisions"][0]["source"] == "branch",
    str([(r["source"], r["chars"]) for r in text["revisions"]]),
)
check(
    "合并后分支仍在",
    call("GET", f"/api/branches/{a['id']}")[0] == 200,
)

# 6. 丢弃 B 案
status, _ = call("DELETE", f"/api/branches/{b['id']}")
remaining = call("GET", f"/api/scenes/{scene['id']}/branches")[1]
check(
    "丢弃分支后主版不变",
    status == 204
    and [row["name"] for row in remaining] == ["A 案"]
    and call("GET", f"/api/scenes/{scene['id']}/text")[1]["body"] == "A 案：他留下来。",
    str([row["name"] for row in remaining]),
)

# 7. 锁定
call("PATCH", f"/api/locks/scene/{scene['id']}", {"locked": True})
status, body = call("POST", f"/api/branches/{a['id']}/merge")
check(
    "锁定场景禁止合并",
    status == 409 and "已锁定" in (body or {}).get("detail", ""),
    f"{status} {body}",
)
check(
    "锁定场景仍可手工保存分支正文",
    call("PUT", f"/api/branches/{a['id']}/body", {"content": "作者自己改的。"})[0] == 200,
)
call("PATCH", f"/api/locks/scene/{scene['id']}", {"locked": False})

# 8. 段落锁
call("PUT", f"/api/scenes/{scene['id']}/paragraph-locks", {"paragraphs": ["必须保留。"]})
call("PUT", f"/api/branches/{a['id']}/body", {"content": "没有那一段。"})
status, body = call("POST", f"/api/branches/{a['id']}/merge")
check(
    "缺已锁段落的分支不能合并",
    status == 409 and "必须保留" in (body or {}).get("detail", ""),
    f"{status}",
)

# 9. 改动历史
history = call("GET", f"/api/projects/{pid}/changes?target_type=scene&target_id={scene['id']}")[1]
summaries = " ".join(row["summary"] for row in history["changes"])
check(
    "历史含开分支 / 合并 / 丢弃",
    "开分支「A 案」" in summaries
    and "合并分支「A 案」" in summaries
    and "丢弃分支「B 案」" in summaries,
    summaries[:160],
)

# 10. 检索不受分支污染
query = urllib.parse.quote("他拔出了枪")
search = call("GET", f"/api/projects/{pid}/search?q={query}")[1]
check("分支正文不进检索", (search or {}).get("results") == [], str(search)[:80])

failed = [row for row in results if not row[1]]
for name, ok, detail in results:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  → {detail}"))
print(f"\n{len(results) - len(failed)}/{len(results)} 通过")
