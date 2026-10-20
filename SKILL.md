---
name: article-study
description: 将外语文章逐句精读为离线 HTML：上原文、下译文/语法/短语，带高亮与“只看原文”切换。注释语言为中文。
---

# article-study — 文章逐句精读（使用手册）

目标
- 将一篇外语文章生成可离线阅读的精读页（单文件 HTML），每句包含：原文、中文译文、语法说明、词组短语（高亮与词汇表）。
- 提供可复现的工作流：抓取 → 生成骨架（analysis.json）→ 编辑 draft.md → 填充 → 注入 → 验收 → 截图与交付。

适用对象
- 使用者：需要把外语文章做逐句精读并交付 HTML 的编辑/教师/助理。
- 协作者 / 子代理：自动化或半自动填稿者（agent）遵循 draft/JSON 契约。
- 维护者：需要扩展语言 playbook、修复模板或验收规则的开发者。

依赖
- Python 3（标准库，无额外第三方依赖）
- （可选）本机有 Chrome 可被脚本用于无头渲染与截图

脚本路径
```
python3 .claude/skills/article-study/article_study.py <子命令> ...
```

快速开始（最短成功路径）
1. 从 URL 生成 HTML 和骨架（analysis.json）与 draft.md：
```
python3 .claude/skills/article-study/article_study.py prep "<URL>" -d article-output
```
2. 编辑生成的 `<名>.draft.md`，按 draft 约定补齐 `zh` 与 `gr` 字段（参见下文契约）。
3. 合并并填充 analysis.json：
```
python3 .claude/skills/article-study/article_study.py fill <名>.draft.md -j analysis.json
```
4. 校验不报错后注入 HTML：
```
python3 .claude/skills/article-study/article_study.py inject <file.html> -j analysis.json
```
5. 验收并截图（可选）：
```
python3 .claude/skills/article-study/article_study.py verify <file.html> -j analysis.json
python3 .claude/skills/article-study/article_study.py shot   <file.html>
```

目录
- 概览（本页）
- 工作流（prep / skeleton / draft / fill / check / inject / verify / shot / open）
- draft.md / analysis.json 契约（字段、校验规则、示例）
- 语言 Playbook（详见 languages/*.md）
- 常见故障与回退策略
- 验收标准与截图说明
- 变更与贡献

---

## 工作流（详细）

1) 取文与生成骨架
- prep: 给定 URL，输出：离线 HTML（图片 base64 内嵌）、analysis.json（骨架）、`<名>.draft.md`（待填）。
  示例：
  `python3 .claude/skills/article-study/article_study.py prep "<URL>" -d article-output`
- skeleton: 用于已有 HTML 时从中提取骨架（不触网）：
  `python3 .claude/skills/article-study/article_study.py skeleton <file.html> -o analysis.json`
- paragraphs: 从 HTML 中按段列出带编号的文本，便于断句检查：
  `python3 .claude/skills/article-study/article_study.py paragraphs <file.html>`

抓取回退顺序（自动）：
1. curl（模拟 Googlebot UA，先直连后走环境代理）
2. headless Chrome 渲染（当 curl 得到空 body / 403 / 406 或被 TLS 指纹阻断时）
3. 正文三路择优：DOM 容器 → Arc XP Fusion.globalContent → schema.org JSON-LD articleBody —— 以字符数量取较多者（阈值 +200 字）

边界分支：付费墙、WAF、人工构造 HTML（脚本提供 render 库函数可用于生成手工骨架）

实体与非正文段（prep 报实体警告时，先用 `paragraphs` 看该段内容再决定处理方式）：
- 末段站方导流（典型 "For more … news, visit our … page"，整段为转义链接）属非正文：从源 HTML 删除该 `<p>`，依次重跑 skeleton 与 draft。
- 正文段残留实体：重跑 skeleton 加 `--normalize` 解码；解码后出现字面包裹标签（`<i>`/`<b>` 等）则剥掉标签保留纯文本，再重跑。

渲染取到标题/配图但正文 0 段（WordPress/Newspack 系站点常见）：
- 信号：prep 的 headless 回退打印「提取段落: 0」，成品 HTML 只有 h1/figure/source；但手动 `curl -A Googlebot` 同一 URL 能拿到完整原始页。
- 原因：正文 `<p class="wp-block-paragraph">` 普遍省略 `</p>`，且段间夹着广告 `<div><broadstreet-zone>`，DOM 解析器取不到干净段落。
- 修法：离线处理（不触网）——从 curl 保存的原始页定位正文容器（如 `class="entry-content"`），按段首标签 `<p class="wp-block-paragraph">` 切点取段，切到下一个 `<hr`/`<div`/`</p>` 为止；丢弃站方捐赠/订阅引导段（典型 "Like what you're reading? … Donate now"）、广告位与 Related 区块；把纯文本段转义后插进 prep 已生成的成品 HTML（保留其 base64 配图），再跑 skeleton。

2) 编辑 draft.md（人工或子代理）
- draft.md 是纯文本格式，按“段.句”编号分组，每个句块包含四字段：en（原文，只读），zh（中文译文，必填），gr（语法分析，必填），ph（短语/搭配��可空），hl（高亮，自动或手动）。

最小示例（单句）：
```
# 0.0
> en: Yesterday, OpenAI fired an answering volley at the conference.
zh: 昨天，OpenAI 在会议上发起了回应。
gr: ｛一般过去时｝fired ...；the output of ... 是｛同位语｝
ph:
- fire a volley | （网球等）截击还击；比喻性的“回击”
hl: fired an answering volley
```
规则要点：
- 每句必须有 `zh` 与 `gr`；`ph` 可空。
- `gr` 书写为要点短语并用全角花括号包裹术语，例如：｛一般过去时｝、｛非限定性定语从句｝。
- `ph` 每条为 `- 英文短语 | 中文释义`，英文短语必须在原句中逐字连续出现。
- `hl`（高亮）优先取 `ph` 的英文列，或手动指定。高亮必须与原文逐字匹配（大小写敏感）。
- 标题/章头（`# T`）若不需分析应整块删除，不留空的 zh/gr。

3) 填充（fill）→ 校验（check）→ 注入（inject）
- fill: 将 draft 的注解合并到 analysis.json 中并就地覆盖（会拦截空字段、格式错误等）
  `python3 .claude/skills/article-study/article_study.py fill <名>.draft.md -j analysis.json`
- check: 只进行静态校验，不写文件，列出全部待修问题：
  `python3 .claude/skills/article-study/article_study.py check <file.html> -j analysis.json`
- inject: 将校验通过的内容注入 HTML 模板并生成注入后的文件（同时保留一份 `<file>.orig.html` 作为回滚源）
  `python3 .claude/skills/article-study/article_study.py inject <file.html> -j analysis.json`

校验原则（check 的三条不变量）：
1. 段落数一致（analysis.json 与 HTML 段落对齐）
2. 同段内各句拼接后覆盖该段全部文字（弯引号/空格差异归一）
3. 每个 `hl` 必能在原文中命中（否则列为不命中项）

注意：check 会一次列出所有问题（字段缺失、句子覆盖失败、所有不命中的 hl），请按列表一次性修完再重跑 check。

4) verify 与截图（shot）
- verify: 进行静态验收断言（句块数、无空 zh/gr、无乱码转义、词汇表去重等）
  `python3 .claude/skills/article-study/article_study.py verify <file.html> -j analysis.json`
- shot: 使用 Chrome/CDP 生成四种全页图（on/off × light/dark）并分片输出供人工核对：
  `python3 .claude/skills/article-study/article_study.py shot <file.html>`

截图产物：
- `*.shot-on.png` / `*.shot-on.dark.png` / `*.shot-off.png` / `*.shot-off.dark.png`（全页长图，文件尺寸可能非常大，禁止直接读入上下文）
- `<名>.parts/`：分片图片（默认 1500px/片），供人工视觉核对用。只用分片来看，不要把整张超长图读回上下文。

完成判据（verify PASS）：
- 高亮与原词对齐，无错位；词汇表完整；source 链接在页脚。
- 深色/浅色模式在首/中/尾片都展示正常。
- 原文模式（off）显示仅原文并保留高亮。

---

## draft.md / analysis.json 契约（详细）

- draft 条目按 `# p.s` 的段号 p 归属（s 仅作定位提示）。同段多组 `> en:` 表示手动拆句；两条 `> en:` 接成一行并合并注释表示合句。
- `en` 由 skeleton 从正文逐字生成；draft 中不要出现 HTML 实体（`&#...;`）——prep/skeleton 已归一化实体。
- `ph` 为二元对：英文短语（must appear exactly in en）与中文释义；不要写成对象形式 `{"en":...,"zh":...}`。
- `analysis.json` 的完整示例见 `example-analysis.json`。

字段说明（简表）：
- en: 原文（只读）
- zh: 中文译文（必填）
- gr: 语法要点/术语（必填）
- ph: 词组列表（可空）
- hl: 高亮短语（可空，缺省取 ph 的英文列）

---

## 语言 Playbook

- 支持语种（在 languages/ 目录下有针对性的 playbook）：
  - en（英语）
  - ja（日本语）
  - ko（韩语）
  - fr, de, es, ru, it, pt, ar, th 等
- 特别说明：脚本优先通过 `<html lang>` 与字符集探测（假名/谚文/阿拉伯/泰文/西里尔等）来判断语种；对非英语语言请参阅对应 playbook 里的断句规则与语法术语表。

语言 playbook 示例链接：
- languages/ja.md、languages/ko.md、languages/fr.md 等

---

## 常见故障与回退策略（快速清单）

1. 抓取为空或被拦截
   - 先用 `paragraphs <file.html>` 检查抓取结果是否包含真实段落。
   - 若遇 WAF 返回“Access Denied”或语言特征异常，尝试手动 headless Chrome 渲染或人工保存页面后使用 `skeleton`。
   - JS 挑战型反爬（如 Datadome：curl 200 但是 bot 提示页、headless Chrome 停在 "Client Challenge"）：启动有界面真 Chrome（临时 `--user-data-dir` + `--remote-debugging-port`），通过 CDP 轮询真实正文选择器直到段数稳定，取 `outerHTML`；随后调用库函数 `extract_page(dom, url)` 与 `render(blocks, ...)` 手工生成离线 HTML，再走 skeleton。注意 blocks 的键为 `p`/`img`/`h2`/`list`（标签栏是 `list` 不是 `ul`）；社论/文章页通常要剔除：标签栏、发布时间行、翻译声明、与正文首段重复的导语 standfirst。
   - 付费墙：三路回退后段落数为 0，或真浏览器过了反爬挑战却只渲染零星正文段并出现 `subscribers only` / `X% of this article left` 计量墙提示（剩余内容服务器端不下发，DOM 与内嵌数据均无全文），均视为硬付费墙，停止并让用户三选一：① 启动受控真浏览器由用户登录订阅账号后取文；② 用户自行保存已解锁页面再走 `skeleton`；③ 换文章。
2. 断句错误（误断或漏断）
   - 在 draft 中手工修断句：多条 `> en:` 连接为一行表示合并；在同段内新增 `# p.s` 来拆句。
   - 对话/报导类插句导致误断：将被插断的语句拼回以覆盖整段，再运行 check。
3. 实体/编码问题（`&amp;#...`）
   - 使用 `skeleton/prep` 的实体归一功能；若仍残留，先用文本编辑器按段替换，再用 check 验证。
4. 注入后表现问题（样式/交互）
   - 注入前先在本地使用 `verify` 断言几何布局（脚本会自动检查横向溢出、徽章遮挡等基本问题）；行为问题需人工或自动化 UI 测试覆盖。

---

## 验收与交付

交付前必须做：
- verify PASS
- 按截图分片人工核对首/中/末三片（浅色与深色模式）确保排版与高亮正确
- 向用户确认是否在浏览器打开精读版；同意则运行：
  `python3 .claude/skills/article-study/article_study.py open <file.html>`
- 复盘并将新发现的可泛化错误模式登记到 `issues.md` 顶部（变更规则）——便于下次避免重复。

交付产物与路径约定：
- 每篇文章的产物放在同一子目录：注入后的 `<file>.html`、`<file>.orig.html`（回滚源）、`analysis.json`、`<名>.draft.md`、`shots/`（截图分片）和 `_media/`（视频/大媒体文件）

---

## 开发与维护（模板 / 移动端约定）

- 注入模板（HTML/CSS/JS）是排版与交互的事实源。改动模板时必须保证：
  - 触摸目标 >= 36px，并加 `touch-action: manipulation`；
  - <=920px 工具栏换行、<=600px 主体布局适配；
  - 不改变 `data-` 系列字段和注入标记（这些字段为脚本定位锚）。

- 若改动模板或截图策略，先在开发分支做一次 end-to-end 验证（prep → fill → inject → verify → shot）并记录差异。

---

## 变更与贡献

- 遇到新的失败模式：先在 `SKILL.md` 对应步骤补充泛化规则，并在 `issues.md` 顶部添加一行日志。
- 增加或修改语言 playbook：在 `languages/` 下新增/更新对应 `xx.md`，并在本文件语言列表中备注主要变化。
- 文档改动流程：建议在新的分支上提交修改并发起 PR，CI（或人工审查）通过后合并。

---

## 示例与参考

- 完整的 JSON 示例：`example-analysis.json`
- 常见问题与排错案例：`issues.md`

---

