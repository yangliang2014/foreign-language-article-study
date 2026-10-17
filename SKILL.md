---
name: article-study
description: 外语文章“逐句精读”（英语/日语/韩语/法语/德语/西班牙语/俄语/意大利语/葡萄牙语/阿拉伯语/泰语）：用户给出文章 URL 要求精读、逐句翻译分析，或给出已抓取的 HTML 要求加逐句双语对照注释时使用。产出离线 HTML，上为外文原句、下为 译文/语法/短语 对照与重点高亮，可一键切换“只看原文”。
---

# article-study 文章逐句精读

把一篇外语文章变成离线 HTML：上下逐句对照（上原文、下 译文/语法/短语），重点高亮，带「只看原文」切换。注释语言始终是中文。

**非英语文章先读对应 playbook**（信源、断句坑、语法术语包、ph 正反例都在里面）。共 11 个语种（英语 + 中国学生热门前 10 外语）：

| 语码 | 语言 | playbook | 断句特点 |
|---|---|---|---|
| en | 英语 | —（本文件即说明） | `. ! ?`+大写 |
| ja | 日语 | [`languages/ja.md`](languages/ja.md) | `。！？` 即断、自动剥注音 |
| ko | 韩语 | [`languages/ko.md`](languages/ko.md) | `. ! ?` 断、无大小写 |
| fr | 法语 | [`languages/fr.md`](languages/fr.md) | 拉丁断句、`« »`、问号前空格 |
| de | 德语 | [`languages/de.md`](languages/de.md) | 拉丁断句、`z. B.` 式缩写、可分动词 |
| es | 西班牙语 | [`languages/es.md`](languages/es.md) | 拉丁断句、`¿ ¡` 倒装标点 |
| ru | 俄语 | [`languages/ru.md`](languages/ru.md) | 拉丁断句、西里尔大写与首字母 |
| it | 意大利语 | [`languages/it.md`](languages/it.md) | 拉丁断句、dott.ssa 式头衔 |
| pt | 葡萄牙语 | [`languages/pt.md`](languages/pt.md) | 拉丁断句、人称不定式 |
| ar | 阿拉伯语 | [`languages/ar.md`](languages/ar.md) | RTL、`. ! ؟`、阿语逗号不断 |
| th | 泰语 | [`languages/th.md`](languages/th.md) | 按空格切分、需大量合句 |

脚本按 `<html lang>` 与文种自动识别语言（假名/谚文/阿拉伯/泰文/西里尔按字符集探测，优先于错标的 html lang），一般无需指定；`fetch`/`prep` 可显式 `--lang en|ja|ko|fr|de|es|ru|it|pt|ar|th`（影响抓取语言头、断句、字体、朗读语音；阿语成品自动 RTL 排版）。日语站常见的 `<ruby><rt>` 注音会被自动剥除。

> **调用必读**：写 draft 与截图核对前，先过一遍同目录 [`issues.md`](issues.md) 顶部的故障信号。

脚本仅依赖 Python 3 标准库：`.claude/skills/article-study/article_study.py`。下文命令均为

```
python3 .claude/skills/article-study/article_study.py <子命令> ...
```

## 工作流

### 1. 取文 + 骨架：URL 用 prep，已有 HTML 用 skeleton

```bash
# URL：一条龙产出 HTML、analysis.json 骨架、待填 draft.md（非英语且自动识别不准时加 --lang <语码>）
python3 .claude/skills/article-study/article_study.py prep "<URL>" -d article-output
python3 .claude/skills/article-study/article_study.py prep "<URL>" -d article-output --lang ja
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
- **WAF 拦截分支**：拿到 200 但内容是拦截页（如 «تم رفض الوصول» / "Access Denied" / 安全验证页），正文看似非 0，**自动回退不会触发**；headless Chrome 多半也被拦（CDP/指纹检测），Wayback 可能被代理墙掉。改用受控真浏览器（browseruse 代理）过挑战后提取正文；正文到手后按下面「手工构造 HTML」处理。
- **手工构造 HTML 分支**：播客单集页等"正文只有简介段"或 WAF 后手工取文的场景，用脚本内 `render([("p", txt)…], title, url, date, None, None, lang=…)` 生成同构 HTML（自带样式/RTL/source 脚注）。两个坑：**必须给 `<h1>`**——没有它 skeleton 的 `title.en` 为空，标题块缺原文（手工写 HTML 时直接加 h1；render 不生成 h1，需手动补）；render 会把 `"` 转义成 `&quot;`，而段落匹配按未解码原文比对，check 会报"找不到句子"——构造后把 `&quot;` 还原为真实引号。
- **抓取异常分支**：先跑 `paragraphs <file.html>` 抽查。若正文挤成一个超大 `<p>`、混入 `window.`/广告脚本碎片或图片署名文字，直接编辑该 HTML：按原文逻辑拆成多个 `<p>`、删净非正文文字，使正文只剩文章本身的段落，再进第 2 步。
- **实体体检分支**：skeleton/prep 会扫描正文 `<p>` 里的 HTML 实体（JSON-LD 源文常带字面 `&#x27;`；浏览器原文模式能解码，但注入时 `en` 经 html-escape 会在精读块里显示成字面文本，check 拦不住）。报警告就加 `--normalize` 重跑（prep 同样支持），脚本就地把源 HTML 正文实体解码成真字符后再生成骨架。**不要手写替换 analysis.json 了事——inject 以源 HTML 为基准重新生成。** 注意：`&lt;i&gt;` 这类**标签实体**解码后变成真 `<i>` 元素留在正文，skeleton 会把内联标签按文字保留，成品显示字面 `<i>`（check/verify 都拦不住，截图才看得出）。正文段落只该剩纯文字：解码后如出现 `<i>/<em>` 等包裹标签，直接从源 HTML 删标签留内容，draft 的 `> en:` 行同步，再走 fill/check/inject。

### 2. 填写 draft.md（助手只写中文，不碰 JSON）

> 下面规则以英语为例；非英语语言的断句复核、`gr` 语法术语包、`ph` 形态正反例见顶部表中对应 playbook。四字段结构与所有校验规则跨语言相同。

draft 是纯文本，每个 `# 段.句` 块长这样（`> en` 只读，装该语言原文，照填下面四行）：

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

`verify` 不依赖肉眼，直接断言注入成品：句块数、无空 zh/gr、无 ph 豆腐块（`en — zh`）、无 `&amp;#…` 双重转义、词汇表条数（`-j` 时对照 JSON 去重短语数）、文末 source 链接存在；并用 CDP 打印真实页高，**还会在 375px 手机视口实测**：整页无横向溢出（无元素出屏）、序号徽章右缘不超过真实首字符 x（盖字）、主按钮 ≥36px / 喇叭 ≥32px 触摸热区（不足为 WARN）。有 FAIL 就修，不进截图。

`shot` 经 CDP 自动测全页高度、原生模拟深色（不再需要手工替换 media 查询），产出：

- 同目录四张全页图：`.shot-on.png` / `.shot-on.dark.png` / `.shot-off.png` / `.shot-off.dark.png`。**全页图是数万像素长条，禁止 Read 进上下文**（既看不清又烧 token）。
- `<名>.parts/` 可读分片（默认 1500px/片）：`on-*` 浅色精读全量分片、`off-*` 浅色原文全量分片、`on-dark-*` 深色精读首/中/尾三片。**截图核对只读分片。**

完成判据（verify PASS 之后，读图只看分片）：

- 浅色：首部、中后段、末部分片都看到——高亮与原词对齐、句子无错位、词汇表完整收尾、source 链接在底；
- 深色：`on-dark-00000` / 中 / 尾三片排版与配色正常；
- 原文模式（`off-*`）：无精读块、只留原文与高亮。

视觉核对同样适合丢给子代理：让它只 Read 指定分片文件并回报异常，别把图片带回主上下文。

**改了注入模板（HTML/CSS/JS 交互、TTS）后**：几何问题 verify 已在 375px 视口自动断言（横向溢出/徽章盖字 FAIL、热区 WARN），但**行为问题测不出**——本地 `python3 -m http.server` 起服用浏览器实测：桌面点一遍切换/全文播放/停止/单句/Ctrl+点击跳句；再用 375px 视口（窄窗或同域 iframe）点一遍手机端按钮、看控制台有无报错（CDP `Runtime.exceptionThrown` 也算）。注入 JS 是单个 IIFE，元素访问必须 null 防御：一处 `null.textContent` 抛错会让页面**所有**按钮同时失效，且静态检查完全看不到。

### 5. 先问用户，再 open 交付

截图核对无误后先问：“是否在浏览器中打开精读版？”**完成判据**：用户同意后执行 `open`，用户拒绝则保留文件并告知路径：

```bash
python3 .claude/skills/article-study/article_study.py open <file.html>
```

### 6. 复盘回写（每次精读结束必做，open 之后）

交付不是终点：对照 [issues.md](issues.md) 顶部故障信号回顾本次精读——

- 遇到**清单没覆盖的新失败模式** → 先把可泛化规则提进本文件对应步骤，再在 issues.md 日志顶部补一行；
- 已有信号覆盖的失败、脚本自动兜住的回退、一次性站点细节 → **不记**。

不回写，同样的坑下次还会踩（本条即为此教训的固化）。

## draft.md / analysis.json 契约

- draft 条目按 `# p.s` 的段号 p 归属（s 仅作定位提示）；同段多组 `> en:` = 手动拆句，两条 en 接成一行并合并注释 = 合句；fill 按 draft 实际条目重建 JSON，句数可以与骨架不同。
- `en` 由 skeleton 从正文逐字生成，弯引号 `’ “ ”` 与真撇号保持原样；实体在第 1 步已归一，draft 里不应再出现 `&#…;`。
- `ph` 每项二元数组语义由 draft 的 `- 英文 | 中文` 保证；手写 JSON 时不要写成 `{"en":..,"zh":..}` 对象（check 不拦，渲染成 `en — zh` 豆腐块，verify 会拦）。
- analysis.json 完整真实范例（49 句）见同目录 `example-analysis.json`。

## 边界与约定

- 脚本是排版与交互（配色、字号、模式切换、配图/h1 显隐、词汇表、打印、截图）的唯一事实源；交付物是填好的 `draft.md`（经 fill 生成 analysis.json）及第 1 步清洗/归一过的源 HTML。
- 注入模板的移动端约定（改模板时必须保持）：触摸目标 ≥36px 并加 `touch-action:manipulation` + 禁 tap 高亮；≤920px 工具栏配置区换行、≤600px 两个主按钮各占半行；刘海/底部 Home 条用 `env(safe-area-inset-*)`；**带尺寸约束（min-width/height 或固定宽高）又带 padding 的控件必须 `box-sizing:border-box`**——`.sn` 曾因 content-box 让 28px 最小宽外加 16px padding 实际占 46px，手机端盖住每句首字母，桌面也仅 4px 侥幸不盖；**flex 收缩链的容器和每一层 item 都要 `min-width:0`**——`.tts-cfg` 曾因自身缺它被两个 select 的内在宽度撑到 432px，375px 下横向溢出 65px、语速框被顶出屏幕（改完验 320/375/390 三宽，verify 已自动测）；TTS 三道防线不可删——首次 touchstart 静音预热解锁 iOS 音频、utterance 秒结束（长句 <300ms onend）判为无引擎、toast 引导「微信/QQ 内置浏览器请用系统浏览器打开」；ana-off（只看原文）模式手机没有 Ctrl/点击，跳回本句靠长按黄色短语（520ms + 震动反馈，捕获阶段拦 click 防误触），桌面 Ctrl/Cmd+点击保留。RTL 语种小屏 padding/序号定位要镜像。
