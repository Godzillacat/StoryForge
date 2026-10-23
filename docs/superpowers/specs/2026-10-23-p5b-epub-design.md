# StoryForge P5b 设计：EPUB 精修

> 2026-10-23。P5 的第二段（P5a 阅读器与朗读已完成；P5c 外壳与打包随后）。
> 产品 §4.8：导出 EPUB 先行，样式模板可配（章节标题、缩进、分页规则）。

## 1. 阶段定义

### 1.1 这一段要解决什么

P2 收尾交付的是**基础版 EPUB**：能读，但只有一条 `content.opf` + N 个章节 xhtml，
没有样式、没有卷层级、没有封面、没有可配的模板。作者拿到的是一个「能打开的文件」，
不是一个「像书的文件」。

P5b 把它做成一本书：

1. **样式模板**：至少两套（素雅 / 传统），控制字体、缩进、行距、章节标题与分页规则。
2. **卷层级**：EPUB 目录要有卷 → 章两级，而不是把卷名塞进章标题里。
3. **封面**：作者给项目指定一张图，EPUB 带上它。
4. **目录**：卷与章都在 nav 里，层级正确。

### 1.2 验收标准

1. **样式模板**
   - 提供 **素雅**（无衬线、段间空行）与 **传统**（衬线、首行缩进两字、章首不缩进）两套。
   - 模板通过 `GET /api/projects/{id}/export?format=epub&template=<key>` 选择；未知模板 400。
   - 样式写进 EPUB 自己的 CSS 文件，**不内联在每章**。
   - 每章 `xhtml` 只带语义标记，样式表统一管外观。
2. **卷层级**
   - `nav.xhtml` 的目录是 `卷 → 章` 两级（卷里没有正文时也要出现，只要有章）。
   - 卷标题在正文里作为独立的**卷扉页**出现（一个 xhtml 或一个带 class 的段落）。
3. **封面**
   - `PUT /api/projects/{id}/cover` 上传图片（PNG / JPEG），`DELETE` 移除。
   - 图片存 `project_assets_dir(project_id)/cover.<ext>`，路径记进既有的 `project.cover_path` 列（该列从 P1a 就在、一直没人读写）。
   - EPUB 的 OPF 带 `<meta name="cover">`、manifest 带 `properties="cover-image"`、spine 第一项是封面页。
   - 没有封面时不伪造一张占位图 —— 直接不带封面页。
   - 上传大小上限 **4 MB**；非图片格式 400；图片在磁盘上按扩展名存，接口返回 `has_cover`。
4. **目录**
   - `nav.xhtml` 与 `toc.ncx`（为兼容老阅读器）都要有，且层级一致。
   - 目录条目用「第 N 卷《卷名》」「第 M 章 章名」，不重复卷名。
5. **基线**：后端 929 条全绿；前端 71 条全绿、`pnpm build` 干净。
6. **本段不调用模型。**

### 1.3 明确不做

- **样式模板的可视化编辑器 / 自定义 CSS** —— 两套内置模板够用；自定义 CSS 是给作品做排版的
  另一层需求，留到真有人要。
- **封面生成**（用 AI 画一张）—— 那是新的模型调用与新的契约，与本段无关。
- **图片正文、脚注、注释、DRM** —— EPUB 的基础版用不到。
- **TXT / Markdown 的样式** —— 纯文本没有样式可言。
- **EPUB 校验器集成**（epubcheck）—— 需要 Java 运行时；用手写测试断言结构。

## 2. 已定决策

| 决策 | 结论 | 理由 |
|---|---|---|
| 模板选择方式 | **查询参数 `template=<key>`，代码常量里的两套** | 与「参数档是代码常量」同一条先例：模板是产品定义，不是作者数据；存进数据库就要迁移、要快照 |
| CSS 放哪 | **`OEBPS/style.css` 一个文件**，每章只 `link` 它 | 内联到每章会让改一处样式要改 N 个文件，且体积翻倍 |
| 卷层级怎么表达 | **卷扉页 xhtml + 两级 nav** | spine 里按顺序排，阅读器自然按顺序翻 |
| 封面存储 | **`project_assets_dir()` + 既有的 `cover_path` 列** | 那一列从 P1a 就有、全仓没人读写 —— 与 `architecture.locked` 当初一样是摆设，正好接上 |
| 上传依赖 | **加 `python-multipart`** | FastAPI 的 `UploadFile` 需要它。这是本段唯一的新依赖，且是官方推荐做法 |
| 封面格式 | **只收 PNG / JPEG** | EPUB 3 的 cover-image 支持这两种最稳妥；WebP 在部分阅读器上不显示 |
| 没有封面时 | **不带封面页**，不伪造 | 假封面比没封面更糟：读者以为那是作者选的 |
| 大小上限 | **4 MB** | 本机图片没必要更大；超了直接拒绝并说明 |
| 老阅读器兼容 | **同时生成 `toc.ncx`** | 便宜的兼容；EPUB2 阅读器只认 ncx |

## 3. 数据

**无新表、无迁移。** `project.cover_path` 早已存在。

- 封面文件落 `%LOCALAPPDATA%\StoryForge\projects\<id>\cover.png|jpg`。
- 删除项目时清理由既有的项目删除路径负责（见实现时的检查）。

## 4. 服务设计

### 4.1 样式模板（`app/epub_styles.py`，纯数据）

```
EPUB_TEMPLATES = {
  "plain":   {"label": "素雅",   ...},
  "classic": {"label": "传统",   ...},
}
template_css(key) -> str
```

素雅：无衬线、段间半行、无首行缩进、章题居中、章前分页。
传统：衬线、首行缩进两字、章题居中、章前分页、卷扉页大标题居中。

### 4.2 EPub 构建（`export_service.build_epub`，重写内部）

结构：

```
mimetype                      （必须第一条、不压缩）
META-INF/container.xml
OEBPS/content.opf             （metadata + manifest + spine）
OEBPS/style.css
OEBPS/cover.xhtml             （有封面时）
OEBPS/cover.png|jpg           （有封面时）
OEBPS/volume-1.xhtml          （卷扉页）
OEBPS/chapter-1.xhtml
...
OEBPS/nav.xhtml               （两级目录）
OEBPS/toc.ncx                 （两级目录，兼容老阅读器）
```

- 章的正文按 `_chapter_text`（与 markdown / txt / book 同一口径）。
- 段落在 `_paragraphs` 里按空行切，**不在服务端套样式**——样式归 CSS。
- 卷扉页只在卷里有正文时生成（否则目录里有卷、正文里没有，翻起来莫名其妙）。

### 4.3 封面（`cover_service.py`）

```
save_cover(session, project_id, filename, data) -> dict   # {has_cover, size, content_type}
clear_cover(session, project_id) -> None
cover_path(session, project_id) -> Path | None
```

- 按魔数判断 PNG / JPEG，**不信扩展名**。
- 写文件用「临时文件 + 替换」，避免半截文件。
- `cover_path` 指向的文件不存在时当作没有封面（用户手工删过）。

### 4.4 API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/projects/{id}/export?format=epub&template=<key>` | 模板可选；未知 400 |
| PUT | `/api/projects/{id}/cover` | multipart 上传，返回 `{has_cover, size}` |
| DELETE | `/api/projects/{id}/cover` | 移除封面（文件不存在也算成功） |

## 5. 前端

- 仪表盘「导出与成品报告」卡片加：**模板下拉**（素雅 / 传统，默认素雅）与 EPUB 下载。
- 同一张卡片加**封面上传 / 移除**：显示当前封面缩略图或「未设置封面」。
- 模板选择**不持久化**（每次导出选一次）—— 见 §1.3，模板是导出参数不是项目设置。

## 6. 测试策略

| 层 | 内容 |
|---|---|
| 模板 | 两套 CSS 都非空且包含关键规则；未知 key 报错 |
| 结构 | mimetype 第一条且 STORED；container / opf / nav / ncx 齐全；spine 顺序 = 卷扉页 → 章 |
| 卷层级 | nav 是两级；无正文的卷不出卷扉页 |
| 封面 | 有封面时 OPF 带 `cover-image` 且 spine 第一项是封面页；无封面时没有封面页；PNG/JPEG 魔数判定；伪造扩展名被拒；超 4MB 被拒；删除后 `has_cover=false` |
| 兼容 | 老结构（无封面、无卷）仍能生成 |
| 前端 | build + 走查（真实点击上传、选模板、下载 EPUB） |

## 7. 风险

- **`python-multipart` 是新依赖** —— 它只用于上传，不影响其它路径。装不上就退化为 base64
  JSON 上传，但那是下策（4MB 的 base64 会让请求体积涨 33%）。
- **封面图片可能很大** —— 4 MB 上限挡住了最坏的；不缩放图片（本机磁盘不是瓶颈，缩放会
  引入 Pillow 这个重依赖）。
- **不同阅读器对 `toc.ncx` 的期望不一致** —— 两套目录都生成，各取所需。
