"""P5c 走查：同源托管、深链回落、单实例、打包自检。临时目录，不调用模型。

需要后端已在 8756 上跑起来（`uv run uvicorn app.main:app --port 8756`），
且前端产物存在（`pnpm build`）。
"""

import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8756"
results: list[tuple[str, bool, str]] = []


def get(path: str):
    try:
        with urllib.request.urlopen(BASE + path) as response:
            return response.status, response.read(), response.headers.get("content-type", "")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), exc.headers.get("content-type", "")


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))


# ---- 1. API 仍然正常 ----
status, body, ctype = get("/api/health")
check("API 正常", status == 200 and b'"status": "ok"' in body.replace(b'"status":"ok"', b'"status": "ok"'),
      f"{status} {body[:60]!r}")

status, body, ctype = get("/api/projects")
check("项目列表是 JSON", status == 200 and "json" in ctype, f"{status} {ctype}")

# ---- 2. 根路径伺服前端产物 ----
status, body, ctype = get("/")
text = body.decode("utf-8", "replace")
check("根路径返回前端页面", status == 200 and "<!doctype html" in text.lower(), f"{status} {text[:60]}")
check("是 html 而不是 json", "html" in ctype, ctype)
check("页面标题是 StoryForge", "<title>StoryForge</title>" in text, text[:200])
check("引用了打包后的 js", "/assets/" in text and ".js" in text, text[:200])

# ---- 3. 静态资源 ----
for path in ("/favicon.svg",):
    status, _body, _ctype = get(path)
    check(f"{path} 可访问", status == 200, str(status))

# ---- 4. 单页应用深链回落 ----
for path in ("/read", "/chapters", "/write", "/world", "/some/deep/unknown/path"):
    status, body, _ctype = get(path)
    page = body.decode("utf-8", "replace")
    check(
        f"深链 {path} 回落到 index.html",
        status == 200 and "<title>StoryForge</title>" in page,
        f"{status} {page[:60]}",
    )

# ---- 5. 未知 API 不回落成 HTML ----
status, body, ctype = get("/api/definitely-not-a-route")
check(
    "未知 API 是 404 且不是 HTML",
    status == 404 and "<!doctype html" not in body.decode("utf-8", "replace").lower(),
    f"{status} {ctype}",
)

# ---- 6. 目录穿越不能读到产物之外 ----
status, body, _ctype = get("/../backend/app/config.py")
leaked = body.decode("utf-8", "replace")
check(
    "目录穿越拿不到产物之外的文件",
    "def data_dir" not in leaked,
    f"{status} {leaked[:60]}",
)

report = {"passed": sum(1 for _, ok, _ in results if ok), "total": len(results)}
failed = [row for row in results if not row[1]]
for name, ok, detail in results:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  → {detail}"))
print(f"\n{report['passed']}/{report['total']} 通过")
print(json.dumps(report))
