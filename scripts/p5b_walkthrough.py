"""P5b 走查：EPUB 模板、卷层级、目录、封面。临时目录，不调用模型。"""

import io
import json
import urllib.error
import urllib.request
import zipfile
from html import escape

BASE = "http://127.0.0.1:8756"
results: list[tuple[str, bool, str]] = []


def call(method: str, path: str, body=None, raw: bytes | None = None, ctype: str | None = None):
    data = raw if raw is not None else (
        json.dumps(body).encode("utf-8") if body is not None else None
    )
    headers = {}
    if data is not None:
        headers["content-type"] = ctype or "application/json"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            payload = response.read()
            return response.status, payload
    except urllib.error.HTTPError as exc:
        payload = exc.read()
        try:
            return exc.code, json.loads(payload)
        except Exception:
            return exc.code, payload


def jget(method: str, path: str, body=None):
    status, payload = call(method, path, body=body)
    return status, (json.loads(payload) if isinstance(payload, bytes) and payload else payload)


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))


def multipart(name: str, filename: str, data: bytes, ctype: str) -> tuple[bytes, str]:
    boundary = "----storyforge-p5b"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
        f"Content-Type: {ctype}\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


# ---- 骨架：两卷三章（其中一章没正文） ----
project = jget("POST", "/api/projects", {"name": "P5b 走查"})[1]
pid = project["id"]
v1 = jget("POST", f"/api/projects/{pid}/volumes", {"name": "起雾"})[1]
v2 = jget("POST", f"/api/projects/{pid}/volumes", {"name": "退潮"})[1]
c1 = jget("POST", f"/api/volumes/{v1['id']}/chapters", {"title": "开端"})[1]
c2 = jget("POST", f"/api/volumes/{v1['id']}/chapters", {"title": "空章"})[1]
c3 = jget("POST", f"/api/volumes/{v2['id']}/chapters", {"title": "转折"})[1]
s1 = jget("POST", f"/api/chapters/{c1['id']}/scenes", {"goal": "开场"})[1]
s2 = jget("POST", f"/api/chapters/{c2['id']}/scenes", {"goal": "空场"})[1]
s3 = jget("POST", f"/api/chapters/{c3['id']}/scenes", {"goal": "转折"})[1]
jget("PUT", f"/api/scenes/{s1['id']}/body", {"content": "雨落在旧城。\n\n第二段。"})
jget("PUT", f"/api/scenes/{s3['id']}/body", {"content": "他推开门。"})


def epub(template: str | None = None) -> zipfile.ZipFile:
    path = f"/api/projects/{pid}/export?format=epub"
    if template:
        path += f"&template={template}"
    status, payload = call("GET", path)
    return zipfile.ZipFile(io.BytesIO(payload))


# ---- 1. 基本结构 ----
plain = epub()
names = plain.namelist()
check("mimetype 是第一条", names[0] == "mimetype", str(names[:3]))
info = plain.getinfo("mimetype")
check("mimetype 不压缩", info.compress_type == zipfile.ZIP_STORED, str(info.compress_type))
check(
    "必需文件齐全",
    {"META-INF/container.xml", "OEBPS/content.opf", "OEBPS/nav.xhtml", "OEBPS/toc.ncx", "OEBPS/style.css"}
    <= set(names),
    str(sorted(set(names))),
)

# ---- 2. 样式只有一份 ----
chapter_page = plain.read("OEBPS/chapter-1.xhtml").decode("utf-8")
check("章里 link 了 style.css", 'href="style.css"' in chapter_page, chapter_page[:120])
check("章里没有内联 <style>", "<style" not in chapter_page)

# ---- 3. 模板切换只换样式 ----
classic = epub("classic")
plain_css = plain.read("OEBPS/style.css")
classic_css = classic.read("OEBPS/style.css")
check("两套模板的 CSS 不同", plain_css != classic_css, f"{len(plain_css)} vs {len(classic_css)}")
check(
    "传统模板首行缩进",
    "text-indent: 2em" in classic_css.decode("utf-8"),
    classic_css[:80].decode("utf-8", "replace"),
)
check(
    "正文内容不随模板变",
    plain.read("OEBPS/chapter-1.xhtml") == classic.read("OEBPS/chapter-1.xhtml"),
)
check(
    "未知模板 400",
    call("GET", f"/api/projects/{pid}/export?format=epub&template=fancy")[0] == 400,
)

# ---- 4. 卷层级与目录 ----
check(
    "两卷各有一张扉页",
    "OEBPS/volume-1.xhtml" in names and "OEBPS/volume-2.xhtml" in names,
    str([n for n in names if "volume" in n]),
)
nav = plain.read("OEBPS/nav.xhtml").decode("utf-8")
check("目录含两卷", "第1卷 起雾" in nav and "第2卷 退潮" in nav, nav[:200])
check("目录是两级（三个 ol）", nav.count("<ol>") == 3, str(nav.count("<ol>")))
check("目录含章", "第1章 开端" in nav and "第1章 转折" in nav)
check("空章不进目录", "空章" not in nav)

opf = plain.read("OEBPS/content.opf").decode("utf-8")
spine = opf.split("<spine", 1)[1]
check(
    "spine 顺序：卷1 → 章1 → 卷2 → 章2",
    spine.index('idref="volume-1"')
    < spine.index('idref="chapter-1"')
    < spine.index('idref="volume-2"')
    < spine.index('idref="chapter-2"'),
    spine[:200],
)

ncx = plain.read("OEBPS/toc.ncx").decode("utf-8")
check("ncx 存在且列章", "<navMap>" in ncx and "第1章 开端" in ncx, ncx[:120])
check("opf 指向 ncx", '<spine toc="ncx">' in opf)
check(
    "ncx 也是两级（卷父 + 章子）",
    ncx.count("<navPoint ") == 4 and 'id="np-volume-1"' in ncx and 'id="np-1"' in ncx,
    str(ncx.count("<navPoint ")),
)
orders = [int(part.split('"')[0]) for part in ncx.split('playOrder="')[1:]]
check(
    "ncx playOrder 连续唯一",
    orders == list(range(1, len(orders) + 1)),
    str(orders),
)

# ---- 5. 正文转义 ----
jget("PUT", f"/api/scenes/{s3['id']}/body", {"content": "<script>alert(1)</script>"})
escaped = epub().read("OEBPS/chapter-2.xhtml").decode("utf-8")
check(
    "HTML 被转义",
    "&lt;script&gt;" in escaped and "<script>alert(1)</script>" not in escaped,
    escaped[-160:],
)
jget("PUT", f"/api/scenes/{s3['id']}/body", {"content": "他推开门。"})

# ---- 6. 封面 ----
png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 128
check("初始没有封面", jget("GET", f"/api/projects/{pid}")[1]["has_cover"] is False)

body, ctype = multipart("file", "cover.png", png, "image/png")
status, _ = call("PUT", f"/api/projects/{pid}/cover", raw=body, ctype=ctype)
check("上传 PNG 成功", status == 200, str(status))
check("上传后 has_cover=true", jget("GET", f"/api/projects/{pid}")[1]["has_cover"] is True)

with_cover = epub()
check(
    "封面图进了包",
    "OEBPS/cover-image.png" in with_cover.namelist(),
    str([n for n in with_cover.namelist() if "cover" in n]),
)
opf_cover = with_cover.read("OEBPS/content.opf").decode("utf-8")
check("opf 带 cover-image", 'properties="cover-image"' in opf_cover)
check('opf 带 <meta name="cover">', '<meta name="cover" content="cover-image"/>' in opf_cover)
spine_cover = opf_cover.split("<spine", 1)[1]
check(
    "封面页排第一",
    spine_cover.index('idref="cover"') < spine_cover.index('idref="volume-1"'),
    spine_cover[:160],
)
cover_page = with_cover.read("OEBPS/cover.xhtml").decode("utf-8")
check("封面页指向真实文件", 'src="cover-image.png"' in cover_page, cover_page[:200])
check(
    "封面页带样式表且整页铺图",
    'href="style.css"' in cover_page and 'class="cover-page"' in cover_page,
    cover_page[:200],
)

# 缩略图接口
status, payload = call("GET", f"/api/projects/{pid}/cover")
check(
    "封面原图可读（仪表盘缩略图用）",
    status == 200 and payload.startswith(b"\x89PNG"),
    f"{status} {payload[:8]!r}",
)

# 非图片被拒
body, ctype = multipart("file", "cover.png", b"not an image", "image/png")
status, payload = call("PUT", f"/api/projects/{pid}/cover", raw=body, ctype=ctype)
check(
    "伪装成 PNG 的非图片被拒",
    status == 400 and "只支持 PNG 或 JPEG" in json.dumps(payload, ensure_ascii=False),
    str(status),
)

# 换格式：旧文件删掉
jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 128
body, ctype = multipart("file", "cover.jpg", jpeg, "image/jpeg")
call("PUT", f"/api/projects/{pid}/cover", raw=body, ctype=ctype)
swapped = epub()
check(
    "换成 JPEG 后旧 PNG 不在包里",
    "OEBPS/cover-image.jpg" in swapped.namelist()
    and "OEBPS/cover-image.png" not in swapped.namelist(),
    str([n for n in swapped.namelist() if "cover" in n]),
)

# 移除封面
check("移除封面 204", call("DELETE", f"/api/projects/{pid}/cover")[0] == 204)
check("移除后 has_cover=false", jget("GET", f"/api/projects/{pid}")[1]["has_cover"] is False)
after = epub()
check(
    "移除后包里没有封面页",
    "OEBPS/cover.xhtml" not in after.namelist()
    and 'properties="cover-image"' not in after.read("OEBPS/content.opf").decode("utf-8"),
)

# ---- 7. 空项目仍是合法 EPUB ----
empty = jget("POST", "/api/projects", {"name": "空书"})[1]
status, payload = call("GET", f"/api/projects/{empty['id']}/export?format=epub")
empty_zip = zipfile.ZipFile(io.BytesIO(payload))
check("空项目也能出 EPUB", status == 200 and empty_zip.namelist()[0] == "mimetype")
check(
    "空项目有占位章",
    "OEBPS/chapter-1.xhtml" in empty_zip.namelist()
    and "尚无正文" in empty_zip.read("OEBPS/chapter-1.xhtml").decode("utf-8"),
)

# ---- 8. 删除项目清掉资产 ----
assets = __import__("os").path.join(
    __import__("os").environ["STORYFORGE_DATA_DIR"], "projects", pid
)
body, ctype = multipart("file", "cover.png", png, "image/png")
call("PUT", f"/api/projects/{pid}/cover", raw=body, ctype=ctype)
check("资产目录存在", __import__("os").path.isdir(assets), assets)
call("DELETE", f"/api/projects/{pid}")
check("删除项目后资产目录也没了", not __import__("os").path.exists(assets), assets)

failed = [row for row in results if not row[1]]
for name, ok, detail in results:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  → {detail}"))
print(f"\n{len(results) - len(failed)}/{len(results)} 通过")
