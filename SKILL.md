---
name: article-study
description: 英文文章“逐句精读”：用户给出文章 URL 要求精读、逐句翻译分析，或给出已抓取的 HTML 要求加逐句双语对照注释时使用。产出离线 HTML，上为英文原句、下为 译文/语法/短语 对照与重点高亮，可一键切换“只看原文”。
---

# article-study 文章逐句精读

仅处理英文文章。把一篇英文文章变成离线 HTML：上下逐句对照（上英文、下 译文/语法/短语），重点高亮，带「只看原文」切换。

> **调用必读**：写 draft 与截图核对前，先过一遍同目录 [`issues.md`](issues.md) 顶部的故障信号。

脚本仅依赖 Python 3 标准库：`.claude/skills/article-study/article_study.py`。下文命令均为

```
python3 .claude/skills/article-study/article_study.py <子命令> ...
```

## 工作流

### 1. 取文 + 骨架：URL 用 prep，已有 HTML 用 skeleton

```bash
# URL：一条龙产出 HTML、analysis.json 骨架、待填 draft.md
python3 .claude/skills/article-study/article_study.py prep "<URL>" -d article-output
# 已有 HTML（只取文不分析时仍可用 fetch）：
python3 .claude/skills/article-study/article_study.py skeleton <file.html> -o analysis.json
python3 .claude/skills/article-study/article_study.py draft -j analysis.json -o <名>.draft.md
python3 .claude/skills/article-study/article_study.py paragraphs <file.html>   # 随时查看带编号正文
```

产出单文件离线 HTML（图片 base64 内嵌；视频落盘到同名 `_media/` 旁挂目录）。一篇文章的 HTML / 备份 / 截图 / JSON / draft 放同一子目录。

抓取按下列顺序自动回退，通常无需干预：

1. **curl**（Googlebot UA，先直连后走环境代理）。
2. **headless Chrome 渲染**：curl 拿到空 body/406/403（边缘按 TLS 指纹拦截非浏览器，换 UA 无效，如 New Scientist）或正文为 0 时，自动用本机 Chrome `--dump-dom` 取渲染后 DOM（可用 `CHROME` 指定浏览器路径；尊重 `http(s)_proxy`）。
3. **正文三路择优**：DOM 容器 → Arc XP `Fusion.globalContent` → schema.org JSON-LD `articleBody`，按正文字符总量取明显更多者（阈值 +200，并列时保留 DOM）。付费墙站点常在 JSON-LD 里放全文供搜索引擎收录（即使 `isAccessibleForFree:false`）；首块若与 `ImageObject.caption` 相同则识别为题图注，短行（≤6 词）识别为小标题；日期兜底取 `datePublished`。

- **付费墙分支**：全部回退后提取段落数仍为 0 才是硬付费墙——停止并告知用户，无正文可分析。
- **抓取异常分支**：先跑 `paragraphs <file.html>` 抽查。若正文挤成一个超大 `<p>`、混入 `window.`/广告脚本碎片或图片署名文字，直接编辑该 HTML：按原文逻辑拆成多个 `<p>`、删净非正文文字，使正文只剩文章本身的段落，再进第 2 步。
- **实体体检分支**：skeleton/prep 会扫描正文 `<p>` 里的 HTML 实体（JSON-LD 源文常带字面 `&#x27;`；浏览器原文模式能解码，但注入时 `en` 经 html-escape 会在精读块里显示成字面文本，check 拦不住）。报警告就加 `--normalize` 重跑（prep 同样支持），脚本就地把源 HTML 正文实体解码成真字符后再生成骨架。**不要手写替换 analysis.json 了事——inject 以源 HTML 为基准重新生成。**

### 2. 填写 draft.md（助手只写中文，不碰 JSON）

draft 是纯文本，每个 `# 段.句` 块长这样（`> en` 只读，照填下面四行）：

```
# 0.0
> en: Yesterday, OpenAI fired an answering volley ...
zh: 昨天，OpenAI 投出一记回击……
gr: ｛一般过去时｝fired/dumped onto…；the output of… 是｛同位语｝
ph:
- fire a volley | （网球等）截击还击；比喻予以回击
- in the form of | 以……的形式
hl: fired an answering volley | a mass campaign against 4000 open problems
```

规则：

1. **每句必填 `zh`、`gr`，`ph` 可空**。
   - `gr` 标时态、从句类型、特殊句式（倒装/强调/with 复合结构/非谓语/分裂不定式等），术语用全角 `｛｝` 包裹，自动渲染高亮。
   - `ph` 每条 `- 英文短语 | 中文释义`，只收真正的固定搭配/习语/短语动词，宁缺毋滥。**英文列必须是该句中的逐字连续片段**：写句中实际出现的变位形式（`lays out`、`struck it rich`、`Rather than`），不要写词典原形（`lay out`、`strike it rich`），禁止 `sb/sth/one's/...` 占位符与省略号模式（`put ... in perspective`）——留空 `hl` 会自动拿英文列做逐字高亮，模式词条必然命中失败。想表达模式义（"把……看作……"）时：ph 英文列写句中短片段（`describe sb as`→`described him as`），释义照旧写概括义；确需高亮跨越多个成分的长片段时，`hl` 显式写句中逐字长片段（可与 ph 英文列不同）。
   - `hl` 用 ` | ` 分隔多个高亮，**留空自动取 ph 英文列**；只收固定搭配时整行不用写。高亮必须是句中连续原文、逐字一致（**大小写敏感**，句首大写要照抄）。
2. **修断句边界与句面文字直接在 draft 里操作**，不用改 JSON：
   - 漏断（词表未覆盖的缩写；`…,” sb said/wrote.` 后紧跟新句）：在同一段内再贴一组 `> en:` + zh/gr/ph/hl（新组自带 `# p.s` 头或直接跟在后面都可以，条目按段归属）。
   - 误断（对话被说话动词插断）：把两条 `> en:` 接成一行、zh/gr/ph/hl 合并成一组，删掉多余的头和行（check 按整段文字覆盖校验）。
   - 整段保守未拆（skeleton 提示 N 段未能自动断句）：同块内手动拆成多组。
   - check 报「段落中找不到句子」且实体已归一时：把该段各句 `> en:` 拼起来与 `paragraphs` 输出的段落文本 diff（弯引号归一）。典型原因是骨架断句源（如 JSON-LD）与最终正文容器不一致，句尾带入段落里不存在的弯引号（`belt.”` → `belt.`）；直接改 `> en:` 行删掉多余字符。
3. 标题块 `# T` 不需要分析就整块删除（不要留空 zh/gr）。
4. 顺序与原文一致；`//` 注释行与空行被忽略，可用于分段标记。

长文（约 >40 句）建议把填写工作放进**子代理**分批做（给 draft 路径与规则，回收合并后的 draft），主上下文不承载整篇英文与译文，省 token 也省时间。子代理提示词必须逐字带上第 1 条的 **ph 英文列逐字规则**并给句中变位形式的正/反例——模型默认会写词典原形（`lay out`、带 `sb/sth`），曾一次产生 88 条不命中，是最大的返工来源。

### 3. fill → check → inject

```bash
python3 .claude/skills/article-study/article_study.py fill  <名>.draft.md -j analysis.json   # 合并并就地覆盖
python3 .claude/skills/article-study/article_study.py check <file.html> -j analysis.json       # 只检查不写文件
python3 .claude/skills/article-study/article_study.py inject <file.html> -j analysis.json      # 就地写入
```

- `fill` 先拦空 zh/gr、ph 不成二元组、越界段号；`hl` 缺省在此补成 ph 英文列。
- **完成判据**：check 输出 OK。校验三条不变量：段落数一致；同段各句拼接覆盖该段**全部**文字（弯引号与空格差异自动归一）；每个 `hl` 都能在句中逐字命中。失败时按提示的段落号改 draft，重跑 fill/check 到 OK 再 inject。
- check 一次列出**全部**问题（字段缺失、句子覆盖、所有不命中的 hl），按清单一轮改完再跑下一次，不要逐条试。
- 首次就地注入自动留一份 `<文件名>.orig.html` 未注入原件，作为只读回滚源。对已注入文件重跑 inject 会自动以它为源覆盖生成——改完 draft 依次重跑 fill/check/inject 即可。

### 4. verify 静态验收 + shot 截图抽查

```bash
python3 .claude/skills/article-study/article_study.py verify <file.html> -j analysis.json
python3 .claude/skills/article-study/article_study.py shot  <file.html>
# 可选：-d 图片目录 -W 宽（默认1300） -H 高（默认0=CDP 自动测全页） -P 分片高（默认1500）；CHROME 指定浏览器
```

`verify` 不依赖肉眼，直接断言注入成品：句块数、无空 zh/gr、无 ph 豆腐块（`en — zh`）、无 `&amp;#…` 双重转义、词汇表条数（`-j` 时对照 JSON 去重短语数）、文末 source 链接存在；并用 CDP 打印真实页高。有 FAIL 就修，不进截图。

`shot` 经 CDP 自动测全页高度、原生模拟深色（不再需要手工替换 media 查询），产出：

- 同目录四张全页图：`.shot-on.png` / `.shot-on.dark.png` / `.shot-off.png` / `.shot-off.dark.png`。**全页图是数万像素长条，禁止 Read 进上下文**（既看不清又烧 token）。
- `<名>.parts/` 可读分片（默认 1500px/片）：`on-*` 浅色精读全量分片、`off-*` 浅色原文全量分片、`on-dark-*` 深色精读首/中/尾三片。**截图核对只读分片。**

完成判据（verify PASS 之后，读图只看分片）：

- 浅色：首部、中后段、末部分片都看到——高亮与原词对齐、句子无错位、词汇表完整收尾、source 链接在底；
- 深色：`on-dark-00000` / 中 / 尾三片排版与配色正常；
- 原文模式（`off-*`）：无精读块、只留原文与高亮。

视觉核对同样适合丢给子代理：让它只 Read 指定分片文件并回报异常，别把图片带回主上下文。

### 5. 先问用户，再 open 交付

截图核对无误后先问：“是否在浏览器中打开精读版？”**完成判据**：用户同意后执行 `open`，用户拒绝则保留文件并告知路径：

```bash
python3 .claude/skills/article-study/article_study.py open <file.html>
```

## draft.md / analysis.json 契约

- draft 条目按 `# p.s` 的段号 p 归属（s 仅作定位提示）；同段多组 `> en:` = 手动拆句，两条 en 接成一行并合并注释 = 合句；fill 按 draft 实际条目重建 JSON，句数可以与骨架不同。
- `en` 由 skeleton 从正文逐字生成，弯引号 `’ “ ”` 与真撇号保持原样；实体在第 1 步已归一，draft 里不应再出现 `&#…;`。
- `ph` 每项二元数组语义由 draft 的 `- 英文 | 中文` 保证；手写 JSON 时不要写成 `{"en":..,"zh":..}` 对象（check 不拦，渲染成 `en — zh` 豆腐块，verify 会拦）。
- analysis.json 完整真实范例（49 句）见同目录 `example-analysis.json`。

## 边界与约定

- 脚本是排版与交互（配色、字号、模式切换、配图/h1 显隐、词汇表、打印、截图）的唯一事实源；交付物是填好的 `draft.md`（经 fill 生成 analysis.json）及第 1 步清洗/归一过的源 HTML。
