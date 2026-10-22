"""P4c 走查：伏笔四态、派生、回收率、未回收口径、逻辑链三类。临时目录，不调用模型。"""

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


# ---- 场景骨架 ----
project = call("POST", "/api/projects", {"name": "P4c 走查"})[1]
pid = project["id"]
volume = call("POST", f"/api/projects/{pid}/volumes", {"name": "第一卷"})[1]
chapter = call("POST", f"/api/volumes/{volume['id']}/chapters", {"title": "第一章"})[1]
plant_scene = call(
    "POST", f"/api/chapters/{chapter['id']}/scenes", {"goal": "埋下录音带"}
)[1]
pay_scene = call("POST", f"/api/chapters/{chapter['id']}/scenes", {"goal": "回收录音带"})[1]

# ---- 1. 词表由后端下发 ----
status, types = call("GET", "/api/foreshadow-types")
keys = [row["key"] for row in (types or {}).get("statuses", [])]
check(
    "词表下发四态",
    status == 200 and keys == ["planned", "planted", "paid", "dropped"],
    f"{status} {keys}",
)
labels = {row["key"]: row["label"] for row in (types or {}).get("statuses", [])}
check(
    "词表中文标签",
    labels.get("paid") == "已收" and labels.get("dropped") == "已弃",
    str(labels),
)

# ---- 2. 建四条伏笔，覆盖四态 ----
def make(name, **fields):
    status, row = call("POST", f"/api/projects/{pid}/foreshadows", {"name": name, **fields})
    return status, row


# 已收：显式 paid
s_paid, f_paid = make("显式已收", status="paid")
# 已埋：显式 planted
s_planted, f_planted = make("显式已埋", status="planted")
# 规划中
s_planned, f_planned = make("还没动")
# 已弃
s_dropped, f_dropped = make("作者放弃", status="dropped")
check("四条伏笔都建成", all(s == 201 for s in (s_paid, s_planted, s_planned, s_dropped)))

# ---- 3. 派生：只设埋设位置，状态仍是 planned → 显示已埋 ----
call("PATCH", f"/api/foreshadows/{f_planned['id']}", {"plan_pay_scene_id": pay_scene["id"]})
status, rows = call("GET", f"/api/projects/{pid}/foreshadows")
by_id = {row["id"]: row for row in rows}
derived = by_id[f_planned["id"]]
check(
    "位置派生：没埋没收时保持规划中",
    derived["effective_status"] == "planned",
    derived["effective_status"],
)

# 给「还没动」挂上埋设位置 → 派生为 planted
call(
    "PATCH",
    f"/api/scenes/{plant_scene['id']}",
    {"foreshadow_plants": ["还没动"]},
)
status, rows = call("GET", f"/api/projects/{pid}/foreshadows")
by_id = {row["id"]: row for row in rows}
derived = by_id[f_planned["id"]]
check(
    "位置派生：挂上埋设位置后显示已埋",
    derived["effective_status"] == "planted"
    and derived["status"] == "planned"
    and derived["status_is_derived"] is True
    and derived["status_label"] == "已埋",
    json.dumps(derived, ensure_ascii=False)[:160],
)

# ---- 4. 显式 planted + 实际回收 → 派生为 paid（事实赢） ----
status, patched = call(
    "PATCH",
    f"/api/foreshadows/{f_planted['id']}",
    {"actual_pay_scene_id": pay_scene["id"]},
)
check(
    "显式已埋 + 有实际回收 → 显示已收",
    status == 200 and patched["effective_status"] == "paid" and patched["status"] == "planted",
    json.dumps(patched, ensure_ascii=False)[:160],
)

# ---- 5. dropped 不被位置字段覆盖 ----
status, patched = call(
    "PATCH",
    f"/api/foreshadows/{f_dropped['id']}",
    {"actual_pay_scene_id": pay_scene["id"]},
)
check(
    "已弃不被实际回收覆盖",
    status == 200 and patched["effective_status"] == "dropped",
    json.dumps(patched, ensure_ascii=False)[:160],
)

# ---- 6. 汇总：四类计数与回收率 ----
status, summary = call("GET", f"/api/projects/{pid}/foreshadows/summary")
check(
    "汇总四类计数",
    status == 200
    and summary["total"] == 4
    and summary["paid"] == 2  # 显式已收 + 显式已埋但有实际回收
    and summary["planted"] == 1  # 位置派生的那条
    and summary["planned"] == 0
    and summary["dropped"] == 1,
    json.dumps(summary, ensure_ascii=False),
)
# 回收率 = paid / (paid + planted + planned) = 2/3
check("回收率不含已弃", summary["rate"] == 0.667, str(summary["rate"]))

# ---- 7. 未知状态被拒 ----
status, body = call("PATCH", f"/api/foreshadows/{f_planned['id']}", {"status": "finished"})
check(
    "未知状态 400 且带可读原因",
    status == 400 and "未知的伏笔状态" in json.dumps(body, ensure_ascii=False),
    f"{status} {json.dumps(body, ensure_ascii=False)[:100]}",
)

# ---- 8. 中文标签也能写入 ----
status, patched = call("PATCH", f"/api/foreshadows/{f_paid['id']}", {"status": "已弃"})
check(
    "中文标签可写入",
    status == 200 and patched["status"] == "dropped",
    f"{status} {patched.get('status')}",
)
call("PATCH", f"/api/foreshadows/{f_paid['id']}", {"status": "paid"})

# ---- 8b. 作者能清掉匹配错的「实际回收」 ----
status, cleared = call(
    "PATCH", f"/api/foreshadows/{f_planted['id']}", {"actual_pay_scene_id": None}
)
check(
    "清掉实际回收后状态退回已埋",
    status == 200
    and cleared["actual_pay_scene_id"] is None
    and cleared["effective_status"] == "planted",
    json.dumps(cleared, ensure_ascii=False)[:160],
)
# 还原，后面的汇总断言按原样算
call("PATCH", f"/api/foreshadows/{f_planted['id']}", {"actual_pay_scene_id": pay_scene["id"]})

# ---- 9. 旧值 confirmed 被标出、归入规划中 ----
status, legacy = make("旧词表遗留")
# 直接写库造旧值：接口会归一成 planned，存量数据才是 confirmed
import sqlite3
import os

db_path = os.path.join(os.environ["STORYFORGE_DATA_DIR"], "storyforge.db")
conn = sqlite3.connect(db_path)
conn.execute("UPDATE foreshadow SET status = 'confirmed' WHERE id = ?", (legacy["id"],))
conn.commit()
conn.close()

status, rows = call("GET", f"/api/projects/{pid}/foreshadows")
legacy_row = next(row for row in rows if row["id"] == legacy["id"])
check(
    "旧值 confirmed 标为 legacy 并归入规划中",
    legacy_row["status_is_legacy"] is True
    and legacy_row["effective_status"] == "planned"
    and legacy_row["status"] == "confirmed",
    json.dumps(legacy_row, ensure_ascii=False)[:160],
)

# ---- 10. 成品报告的「未回收」不再算已弃 ----
call("PUT", f"/api/scenes/{plant_scene['id']}/body", {"content": "他埋下了录音带。"})
status, report = call("GET", f"/api/projects/{pid}/export/report")
names = [row["name"] for row in (report or {}).get("unrecovered_foreshadows", [])]
check(
    "报告未回收不含已弃与已收",
    status == 200 and "作者放弃" not in names and "显式已收" not in names,
    str(names),
)
check(
    "报告未回收含已埋未收的那条",
    "还没动" in names or "旧词表遗留" in names,
    str(names),
)

# ---- 11. 逻辑链：三类 + 段落序号 ----
body = (
    "雨停在午夜。\n\n"
    "因为他听见了脚步声，所以他停下了。\n\n"
    "他以为安全了。但是门外有人。\n\n"
    "他推开门。原来屋里一直有人。"
)
call("PUT", f"/api/scenes/{plant_scene['id']}/body", {"content": body})
status, chain = call("GET", f"/api/scenes/{plant_scene['id']}/logic-chain")
kinds = [item["kind"] for item in chain["chain"]]
check(
    "逻辑链抽出三类",
    status == 200 and kinds == ["cause", "turn", "reveal"],
    f"{status} {kinds}",
)
check(
    "段落序号按非空段落计",
    [item["paragraph"] for item in chain["chain"]] == [2, 3, 4],
    str([item["paragraph"] for item in chain["chain"]]),
)
check(
    "汇总按类型计数",
    chain["summary"] == {"total": 3, "cause": 1, "turn": 1, "reveal": 1},
    str(chain["summary"]),
)
check(
    "每句带连接词与中文类型名",
    chain["chain"][0]["marker"] == "因为" and chain["chain"][0]["kind_label"] == "因果",
    json.dumps(chain["chain"][0], ensure_ascii=False),
)

# ---- 12. 没有正文 / 没有连接词 ----
empty_scene = call("POST", f"/api/chapters/{chapter['id']}/scenes", {"goal": "空场"})[1]
status, empty = call("GET", f"/api/scenes/{empty_scene['id']}/logic-chain")
check(
    "空正文给出原因而不是空列表",
    status == 200 and empty["chain"] == [] and empty["reason"] != "",
    f"{status} {empty['reason']}",
)

call("PUT", f"/api/scenes/{empty_scene['id']}/body", {"content": "雨停了。他走出门。天很蓝。"})
status, plain = call("GET", f"/api/scenes/{empty_scene['id']}/logic-chain")
check(
    "没有连接词时不硬凑",
    status == 200 and plain["chain"] == [] and "没有明显" in plain["reason"],
    f"{status} {plain['reason']}",
)

# ---- 13. 不存在的场景 404 ----
check("不存在的场景 404", call("GET", "/api/scenes/nope/logic-chain")[0] == 404)

failed = [row for row in results if not row[1]]
for name, ok, detail in results:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  → {detail}"))
print(f"\n{len(results) - len(failed)}/{len(results)} 通过")
