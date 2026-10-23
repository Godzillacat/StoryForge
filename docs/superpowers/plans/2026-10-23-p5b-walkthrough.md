# P5b 走查记录：EPUB 精修

> 2026-10-23。分支 `worktree-p5b-epub`。走查全程使用临时数据目录
> （`STORYFORGE_DATA_DIR`），**未调用模型**、**未写入作者真实库**。

## 1. 自动化测试

| 项 | 结果 |
|---|---|
| 后端 | **969 passed**（基线 929，本段新增 40） |
| 前端 | **71 passed**（本段未改前端测试） |
| 前端构建 | `pnpm build` 干净 |

## 2. 接口级走查（`scripts/p5b_walkthrough.py`，39 项全过）

| 组 | 覆盖 |
|---|---|
| 基本结构 | mimetype 第一条且不压缩；container / opf / nav / ncx / style.css 齐全 |
| 样式 | 章里 `link` 了 style.css、没有内联 `<style>`；两套模板 CSS 不同且正文不变；未知模板 400 |
| 卷层级 | 两卷各一张扉页；spine 顺序 卷1 → 章1 → 卷2 → 章2 |
| 目录 | nav 与 **ncx 都是两级**（ncx 4 个 navPoint、playOrder 连续唯一）；含卷含章、空章不进；opf 指向 ncx |
| 转义 | 正文里的 `<script>` 变成 `&lt;script&gt;` |
| 封面 | 上传 PNG / 换 JPEG 后旧文件消失 / 伪装成 PNG 的非图片被拒 / 移除后 `has_cover=false` 且包里无封面页 / 封面页带样式表且整页铺图 / 原图接口可读 |
| 空项目 | 仍出合法 EPUB，带一章占位 |
| 清理 | 删除项目后资产目录一并消失 |

## 3. 浏览器走查（Playwright + msedge）

后端 8756、前端 5278（`--port` 被占用时 Vite 会自动顺延，第一次走查就落在旧端口上、
看到的其实是旧 bundle —— 现在改成先读日志里的实际端口再打开）。

| 项 | 结果 |
|---|---|
| 模板下拉 | 「素雅 / 传统」；切到传统后 EPUB 链接变成 `&template=classic` |
| 封面空态 | 「未设置封面，EPUB 不会带封面页」+ 上传按钮 |
| 真实上传 | 选一张真 PNG → 出现**缩略图**与「换一张 / 移除」，**导出卡片不塌** |
| EPUB 带封面 | 包里 `cover-image.png` + `cover.xhtml`；opf 有 `cover-image` 与 `<meta name="cover">`；spine 第一项是封面页 |
| 移除 | 点「移除」后回到未设置态 |
| 控制台 | 0 ERROR |

## 4. 未覆盖 / 遗留

- **没有用真实阅读器打开验收**：结构断言是手写的（epubcheck 要 Java 运行时）。
  真机阅读器（Calibre / 微信读书 / Apple Books）的表现未验。
- **封面不缩放**：4 MB 以内原样打包。缩放要引入 Pillow 这个重依赖。
- **目录不折叠**：卷节点在 nav 里是父节点，但是否折叠由阅读器决定，我们控制不了。
- **模板只有两套**：自定义 CSS 与可视化排版编辑器不做。
- **缩略图走的是原图**：`GET /api/projects/{id}/cover` 直接回原文件，几 MB 以内本机
  回环不构成问题；不做服务端缩放（那要引入 Pillow）。
