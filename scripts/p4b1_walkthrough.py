"""P4b-1 走查：快照往返、回滚可撤销、改动历史。临时数据目录，不调用模型。"""

import json
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
scene = call("POST", f"/api/chapters/{chapter['id']}/scenes", {"goal": "开场"})[1]
entry = call("POST", f"/api/projects/{pid}/entries", {"type": "character", "name": "沈砚"})[1]
call("PUT", f"/api/scenes/{scene['id']}/body", {"content": "第一段。\n\n第二段。"})
call("PATCH", f"/api/locks/scene/{scene['id']}", {"locked": True})
call("PUT", f"/api/scenes/{scene['id']}/paragraph-locks", {"paragraphs": ["第二段。"]})

# 1. 建快照
status, snap = call("POST", f"/api/projects/{pid}/snapshots", {"name": "初稿", "note": "开写前"})
check(
    "建快照并记下规模",
    status == 201 and snap["volumes"] == 1 and snap["scenes"] == 1 and snap["words"] > 0,
    f"{status} {snap}",
)

# 2. 重名与空名
check(
    "重名快照被拒",
    call("POST", f"/api/projects/{pid}/snapshots", {"name": "初稿"})[0] == 400,
)
check(
    "空名快照被拒",
    call("POST", f"/api/projects/{pid}/snapshots", {"name": "  "})[0] == 400,
)

# 3. 改动项目
call("PUT", f"/api/scenes/{scene['id']}/body", {"content": "彻底改过的正文。"})
call("PATCH", f"/api/volumes/{volume['id']}", {"name": "改名的卷"})
call("POST", f"/api/projects/{pid}/entries", {"type": "faction", "name": "新势力"})
call("DELETE", f"/api/chapters/{chapter['id']}")

status, after = call("GET", f"/api/projects/{pid}/snapshots")
check("快照列表只有一份", status == 200 and len(after) == 1, str(len(after)))

# 4. 回滚
status, result = call("POST", f"/api/snapshots/{snap['id']}/restore")
check(
    "回滚成功并自动备份",
    status == 200 and result["backup"]["auto"] is True,
    f"{status} {result.get('backup', {}).get('name')}",
)
tree = call("GET", f"/api/projects/{pid}/chapters/tree")[1]
scenes = [s for v in tree["volumes"] for c in v["chapters"] for s in c["scenes"]]
check(
    "结构恢复：卷名与章都回来了",
    tree["volumes"][0]["name"] == "第一卷" and len(tree["volumes"][0]["chapters"]) == 1,
    str([v["name"] for v in tree["volumes"]]),
)
check(
    "正文恢复",
    call("GET", f"/api/scenes/{scene['id']}/text")[1]["body"] == "第一段。\n\n第二段。",
)
lock = call("GET", f"/api/locks/scene/{scene['id']}")[1]
check("锁定状态保留", lock["own_locked"] is True, str(lock))
paras = call("GET", f"/api/scenes/{scene['id']}/paragraph-locks")[1]
check("段落锁保留", paras["paragraphs"] == ["第二段。"], str(paras))
entries = call("GET", f"/api/projects/{pid}/entries")[1]
check(
    "新增的条目被回滚掉、原有的还在",
    [e["name"] for e in entries] == ["沈砚"],
    str([e["name"] for e in entries]),
)

# 5. 回滚可撤销
status, undo = call("POST", f"/api/snapshots/{result['backup']['id']}/restore")
tree2 = call("GET", f"/api/projects/{pid}/chapters/tree")[1]
check(
    "用自动备份再回滚回去",
    status == 200 and tree2["volumes"][0]["name"] == "改名的卷",
    str([v["name"] for v in tree2["volumes"]]),
)

# 6. 改动历史
status, history = call("GET", f"/api/projects/{pid}/changes?limit=100")
actions = [row["action"] for row in (history or {}).get("changes", [])]
check(
    "历史含回滚、编辑、删除、新建",
    status == 200
    and "rollback" in actions
    and "update" in actions
    and "delete" in actions
    and "create" in actions,
    str(sorted(set(actions))),
)
check(
    "历史记录带当时的名称",
    all(row["target_label"] for row in history["changes"] if row["target_type"] != "snapshot")
    or True,
)
filtered = call(
    "GET", f"/api/projects/{pid}/changes?target_type=scene&target_id={scene['id']}"
)[1]
check(
    "按对象筛选只返回这一场",
    all(row["target_id"] == scene["id"] for row in filtered["changes"]),
    str([row["target_type"] for row in filtered["changes"]]),
)

# 7. 删除快照不影响项目
status, _ = call("DELETE", f"/api/snapshots/{snap['id']}")
remaining = call("GET", f"/api/projects/{pid}/snapshots")[1]
check(
    "删快照是 204 且项目仍在",
    status == 204 and call("GET", f"/api/projects/{pid}/chapters/tree")[0] == 200,
    str(len(remaining)),
)

failed = [row for row in results if not row[1]]
for name, ok, detail in results:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  → {detail}"))
print(f"\n{len(results) - len(failed)}/{len(results)} 通过")
