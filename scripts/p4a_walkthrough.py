"""P4a 走查：锁定拦截、影响面、待复核、导出报告。临时数据目录，不调用模型。"""

import json
import os
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8799"
DATA_DIR = Path(os.environ["STORYFORGE_DATA_DIR"])
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
s1 = call("POST", f"/api/chapters/{chapter['id']}/scenes", {"goal": "开场"})[1]
s2 = call("POST", f"/api/chapters/{chapter['id']}/scenes", {"goal": "转折"})[1]
entry = call("POST", f"/api/projects/{pid}/entries", {"type": "character", "name": "沈砚"})[1]
call("PATCH", f"/api/scenes/{s1['id']}", {"characters": ["沈砚"]})
call("PUT", f"/api/scenes/{s2['id']}/body", {"content": "沈砚走进雨里。\n\n他没有回头。"})

# 1. 锁定目标清单
status, targets = call("GET", "/api/lock-targets")
check(
    "锁定目标清单由后端下发",
    status == 200 and len(targets["targets"]) == 5,
    str(targets),
)

# 2. 锁定场景
status, state = call("PATCH", f"/api/locks/scene/{s1['id']}", {"locked": True})
check("场景可锁定", status == 200 and state["own_locked"] is True, str(state))

# 3. 锁定后生成被拒（409，且没有花钱）
status, body = call("POST", f"/api/scenes/{s1['id']}/generate")
check(
    "锁定场景生成被 409 拒绝",
    status == 409 and "已锁定" in (body or {}).get("detail", ""),
    f"{status} {body}",
)

# 4. 未锁场景不受影响（这里只验证它不走 409 —— 无服务商时是 400）
status, body = call("POST", f"/api/scenes/{s2['id']}/generate")
check("未锁场景不被锁定拦截", status != 409, f"{status} {(body or {}).get('detail','')}")

# 5. 采纳被拒
def seed_draft(scene_id: str, content: str) -> None:
    """草稿没有「新建」接口（由生成产生）；走查在临时库里直接插一条。"""
    import sqlite3
    import uuid

    conn = sqlite3.connect(str(DATA_DIR / "storyforge.db"))
    conn.execute(
        "INSERT INTO scene_draft (id, scene_id, run_id, content, created_at, updated_at)"
        " VALUES (?, ?, NULL, ?, datetime('now'), datetime('now'))"
        " ON CONFLICT(scene_id) DO UPDATE SET content = excluded.content",
        (str(uuid.uuid4()), scene_id, content),
    )
    conn.commit()
    conn.close()


seed_draft(s1["id"], "草稿。")
status, body = call("POST", f"/api/scenes/{s1['id']}/adopt")
check(
    "锁定场景采纳被 409 拒绝",
    status == 409 and "已锁定" in (body or {}).get("detail", ""),
    f"{status} {body}",
)

# 6. 段落锁
status, body = call(
    "PUT", f"/api/scenes/{s2['id']}/paragraph-locks", {"paragraphs": ["他没有回头。"]}
)
check(
    "段落锁保存",
    status == 200 and body["paragraphs"] == ["他没有回头。"],
    str(body),
)
seed_draft(s2["id"], "完全不同的正文。")
status, body = call("POST", f"/api/scenes/{s2['id']}/adopt")
check(
    "缺少已锁段落的草稿被拒绝采纳",
    status == 409 and "他没有回头" in (body or {}).get("detail", ""),
    f"{status} {body}",
)
seed_draft(s2["id"], "新的开头。\n\n他没有回头。")
status, body = call("POST", f"/api/scenes/{s2['id']}/adopt")
check(
    "保留已锁段落的草稿可以采纳",
    status == 200 and "他没有回头" in (body or {}).get("body", ""),
    f"{status}",
)

# 7. 作者手工保存不受锁限制
status, body = call("PUT", f"/api/scenes/{s1['id']}/body", {"content": "作者自己写的。"})
check(
    "作者手工保存不受锁定限制",
    status == 200 and body["body"] == "作者自己写的。",
    f"{status}",
)

# 8. 影响面
status, impact = call(
    "GET", f"/api/projects/{pid}/impact?target_type=entry&target_id={entry['id']}"
)
groups = {group["key"]: group for group in (impact or {}).get("groups", [])}
check(
    "条目影响面列出出场场景",
    status == 200 and groups["scenes"]["total"] == 1,
    f"{status} scenes={groups.get('scenes', {}).get('total')}",
)
check(
    "条目影响面列出正文提到的场景",
    groups.get("mentions", {}).get("total", 0) >= 1,
    str([item["label"] for item in groups.get("mentions", {}).get("items", [])]),
)
check(
    "影响面标出锁定数",
    groups.get("scenes", {}).get("locked") == 1,
    str(groups.get("scenes", {}).get("locked")),
)

status, impact = call(
    "GET", f"/api/projects/{pid}/impact?target_type=volume&target_id={volume['id']}"
)
check(
    "卷影响面列出章与场景",
    status == 200
    and {g["key"] for g in impact["groups"]} >= {"chapters", "scenes"},
    str([g["key"] for g in (impact or {}).get("groups", [])]),
)

status, impact = call(
    "GET", f"/api/projects/{pid}/impact?target_type=scene&target_id={s2['id']}"
)
check(
    "场景影响面列出草稿与修订",
    status == 200 and any(g["key"] == "drafts" for g in impact["groups"]),
    str([g["key"] for g in (impact or {}).get("groups", [])]),
)

# 9. 待复核
status, added = call(
    "POST",
    f"/api/projects/{pid}/review-marks",
    {
        "items": [
            {"target_type": "scene", "target_id": s1["id"], "reason": "架构已改"},
            {"target_type": "chapter", "target_id": chapter["id"], "reason": "架构已改"},
        ]
    },
)
check("标为待复核", status == 200 and added["added"] == 2, str(added.get("added")))
status, again = call(
    "POST",
    f"/api/projects/{pid}/review-marks",
    {"items": [{"target_type": "scene", "target_id": s1["id"]}]},
)
check("重复标记幂等", again["added"] == 0, str(again["added"]))

marks = call("GET", f"/api/projects/{pid}/review-marks")[1]
check(
    "待复核带标签与路径",
    all(mark["label"] and mark["path"] for mark in marks),
    str([(m["label"], m["path"]) for m in marks]),
)

status, cleared = call(f"DELETE", f"/api/review-marks/{marks[0]['id']}")
check("单条清除待复核", status == 204, str(status))
remaining = call("GET", f"/api/projects/{pid}/review-marks")[1]
status, bulk = call(
    "POST",
    f"/api/projects/{pid}/review-marks/clear",
    {
        "items": [
            {"target_type": m["target_type"], "target_id": m["target_id"]}
            for m in remaining
        ]
    },
)
check(
    "批量清除待复核",
    status == 200 and bulk["removed"] == len(remaining) and bulk["marks"] == [],
    f"{status} removed={bulk.get('removed')} expected={len(remaining)}",
)

# 10. 导出报告
report = call("GET", f"/api/projects/{pid}/export/report")[1]
check(
    "导出报告含锁定状态",
    report.get("locked_counts", {}).get("scenes") == 1,
    str(report.get("locked_counts")),
)
check(
    "导出报告含待复核数",
    "review_marks" in report,
    str(report.get("review_marks")),
)

# 11. 章纲替换写入被拒
status, body = call(
    "PUT",
    f"/api/projects/{pid}/chapters",
    {"mode": "replace", "volumes": [{"name": "新卷", "chapters": []}]},
)
check(
    "含锁定场景时替换章纲被 409 拒绝",
    status == 409 and "已锁定" in (body or {}).get("detail", ""),
    f"{status} {body}",
)

# 12. 解锁后恢复
call("PATCH", f"/api/locks/scene/{s1['id']}", {"locked": False})
status, body = call(
    "PUT",
    f"/api/projects/{pid}/chapters",
    {"mode": "replace", "volumes": [{"name": "新卷", "chapters": [{"title": "新章"}]}]},
)
check("解锁后替换章纲恢复可用", status == 200, f"{status}")

failed = [row for row in results if not row[1]]
for name, ok, detail in results:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  → {detail}"))
print(f"\n{len(results) - len(failed)}/{len(results)} 通过")
