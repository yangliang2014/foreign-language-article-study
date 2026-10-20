# issues.md — 精读踩坑诊断

写 draft 和截图核对前过一遍下面的**故障信号**。规则与修法在 SKILL.md（唯一出处），这里只列信号本身和定位线索。

## 故障信号

- 短语/词汇表显示成字面 **`en — zh`** 或方框 → ph 写成了 dict 对象；draft 流程从语法上杜绝，手写 JSON 才会发生，verify 必拦。
- verify FAIL **`&amp;#…` 双重转义**，或 skeleton 打印 **实体警告** → 源文正文残留 HTML 实体，修法见 SKILL.md「实体体检分支」。
- 某句读着是两句话却只有一个编号（典型：`…,” sb said/wrote on X. Surprisingly/And …`）→ skeleton 漏断，在 draft 同一块内加一组 `> en:`。
- check 连续报「高亮短语在句中找不到」、ph 看着却"没错"（`lay out`、`put ... in perspective`、带 `sb/sth`）→ ph 写了词典原形而非句中逐字片段；规则见 SKILL.md 第 2 步，check 会一次列全所有不命中。
- check 报「段落中找不到句子」、实体也已归一过 → 骨架 `> en:` 句尾带了正文容器里不存在的字符；定位法见 SKILL.md 第 2 步。
- 精读块出现字面 **`<i>`/`</i>` 标签文本**（截图核对才可见）→ 源文 JSON-LD 自带实体编码标签，`--normalize` 解码后成真标签被 skeleton 按文字保留；从源 HTML 剥掉包裹标签留纯文本，draft `> en:` 同步重跑，见 SKILL.md 第 1 步「实体与非正文段」。
- prep 实体警告落在**末段站方导流**（`For more … news, visit our … page`，整段为转义链接）→ 非正文，按 SKILL.md 第 1 步「实体与非正文段」删段重跑。
- 抓到 **200 但内容是 WAF 拦截页**（«تم رفض الوصول» / "Access Denied"，正文非 0）→ 自动回退不触发，headless Chrome 也拦；改受控真浏览器取文，见 SKILL.md 第 1 步 WAF 拦截分支。
- 真浏览器过了反爬挑战但正文只有零星几段、出现 **"You have X% of this article left … subscribers only"** 计量墙提示 → 硬付费墙（段数非 0，三路探测不触发），按 SKILL.md 第 1 步付费墙分支处理。
- 手工 render 后成品标题下出现**重复标签栏/发布时间/翻译声明**（截图首片才可见）→ blocks 过滤漏项，标签栏块键是 `list`，按 SKILL.md 第 1 步 JS 挑战分支的块类型清单剔除后重渲染。
- 手工构造 HTML 后 **skeleton 的 `title.en` 为空**（标题块缺原文）或 **check 报段落找不到句子但实体已归一、`&quot;` 字样在源 HTML 里** → 见 SKILL.md 第 1 步手工构造分支（h1 必需；render 转义需还原）。
- prep 渲染到标题+配图但**提取段落 0**（成品只有 h1/figure/source），手动 curl Googlebot 同 URL 却能拿到完整页 → WordPress/Newspack 系省略闭合标签，修法见 SKILL.md 第 1 步「渲染取到标题/配图但正文 0 段」。
- 想 Read 全页截图核对 → 停，只读 `<名>.parts/` 分片（原因见 SKILL.md 第 4 节）。
- 手机端**所有按钮同时失效**（模式切换、播放全点不动）→ 注入 IIFE 里某处元素访问无 null 防御抛错，静态检查看不到；改模板后必须浏览器实测（SKILL.md 第 4 节）。
- 手机端 TTS **点了没声音也没提示** → iOS 微信/QQ 内置 WKWebView 无 TTS 引擎或音频通道未解锁；模板已有预热/秒结束检测/toast 引导三道防线，改 JS 时勿删（SKILL.md「边界与约定」移动端约定）。
- 手机端**句首字母被绿色序号徽章盖住**（如 "1 ettling"）或**整页能横向拖动、某控件被顶出屏外**（375px 工具栏只见语音框、语速框消失）→ 控件盒模型/flex 收缩链问题，规则见 SKILL.md「边界与约定」；verify 的 375px 视口审计直接 FAIL。

## 日志（最新在前，一行：站点 — 症状 → 现在由什么兜住）

- 2026-10-20 · New England Times 长文《The REZ environmental damage the law allows》（104 段/195 句）— 句数过百后三位数序号徽章比两位宽，375px 审计在句 115 等 5 处抓到徽章盖句首 → 移动端 `.sa-en` padding-left 46→58px、徽章 min-width 28→30px；该审计对成品实际句数运行，超百句页面自动覆盖。

- 2026-10-20 · New England Times《More than 3,000 items ... regional NSW》— headless 渲染提取段落 0（WP 站 `<p class="wp-block-paragraph">` 省略 `</p>` + 段间广告 div），curl 直连完整 → SKILL.md 第 1 步新增「渲染取到标题/配图但正文 0 段」离线切点取段流程。

- 2026-10-17 · Le Monde EN 社论《Mélenchon's alternative budget》— Datadome 挑战（curl bot 页 / headless Client Challenge）+ 手工 render 漏过标签栏 → 有界面真 Chrome + CDP 轮询取文、按块类型清单过滤，见 SKILL.md 第 1 步 JS 挑战分支。

- 2026-10-17 · Le Monde EN《Gen Z's unique humor ...》— curl 200 实为 Datadome bot 页、headless Chrome 得 Client Challenge；有界面真 Chrome 过挑战后撞计量墙（仅 2 段 + "81.52% left / subscribers only"），Google 来源、Wayback/archive.ph 均无全文 → 用户选择换篇；SKILL.md 付费墙判据扩展为「段落 0 或 subscribers-only 计量墙」并给出登录/自存/换篇三选一，issues 加两条信号（bot 200 已有、计量墙新增）。

- 2026-10-17 · CTV News《Man arrested for N.B. homicide ... Dubai》— prep 实体警告命中末段站方导流（转义链接）→ SKILL.md 第 1 步新增「实体与非正文段」分支：导流段删段重跑、正文实体才 normalize；issues 加信号行。

- 2026-10-17 · 脚本改进（CTV 篇 375px 手机端）— 序号徽章 content-box 撑大盖住每句首字母（桌面仅 4px 间隙侥幸没盖）；`.tts-cfg` 收缩链缺 `min-width:0` 横向溢出 65px、语速下拉出屏 → 相关控件 `box-sizing:border-box`、flex 链全层 `min-width:0`、≤600px 两 select 等宽、热区 34px；verify 新增 375px CDP 审计（溢出/盖字 FAIL、热区 WARN），负向样例实测可抓；规则上提 SKILL.md 边界约定。
- 2026-10-17 · 脚本改进（三语成品手机端故障）— 手机上模式切换/播放全失效：注入 IIFE 无 null 防御，一处抛错全瘫；iOS 微信/QQ 无 TTS 引擎时静默失败；触摸目标 33px、窄屏挤压、只看原文无 Ctrl 键跳句、无安全区适配 → 全元素 null 防御 + TTS 预热/秒结束检测/toast 三道防线 + ≥36px 热区 + 600/920px 断点 + 长按黄色短语跳句 + safe-area-inset；SKILL.md 第 4 节加「改模板必须浏览器实测」、边界约定加移动端清单。
- 2026-10-15 · Al Arabiya《الكلام خليجي》播客单集 — curl 与 headless Chrome 均被 WAF 拦（200 + «تم رفض الوصول»），Wayback 走代理 502；受控真浏览器过审取到正文。手工构造 HTML 又踩两坑：无 `<h1>` 致 `title.en` 空、`render()` 转义 `"` 致 check 找不到句子 → SKILL.md 第 1 步新增「WAF 拦截分支」与「手工构造 HTML 分支」（h1 已实测验证）。
- 2026-10-15 · CTV News《U.S. grand jury indicts James Bryant》— JSON-LD 正文带 `&lt;i&gt;` 标签实体，`--normalize` 解码后 `<i>` 以字面文本渲染进成品，check/verify 均拦不住，截图才暴露 → SKILL.md 第 1 步实体分支补「剥包裹标签」规则。
- 2026-10-15 · 脚本改进（NatGeo 篇返工耗时）— check 每轮只报第一个 hl，88 条错误要跑很多轮 → `validate_analysis` 渲染前聚合校验，一次列出字段/覆盖/全部 hl 错误。
- 2026-10-15 · National Geographic《Philbrick 淘金热访谈》— 子代理填的 ph 全是词典原形/`sb/sth` 模式，88 条高亮不命中，check 每次只报一条 → SKILL.md 第 2 步 ph 逐字规则 + 第 3 步 fill 前全量子串审计。
- 2026-10-15 · 同篇 — check 报第 8 段找不到句子，`--normalize` 后仍失败（断句取 JSON-LD、正文取 DOM，句尾 `.”` 只存于前者）→ SKILL.md 第 2 步拼接 diff 定位、改 draft 的 `> en:`。
- 2026-10-15 · New Scientist《dumped 722 maths papers》— 精读块出现字面 `doesn&#x27;t`，check 与原文模式都正常 → skeleton 实体体检 + `--normalize`，verify 兜底。
- 2026-10-15 · 同篇 — ph 写成 dict，check 通过但全篇渲染成 `en — zh` → draft DSL 语法杜绝 + verify 断言。
- 2026-10-15 · 同篇 — 末段 `…he wrote on X. Surprisingly…` 并成一句 → draft 块内加 `> en:` 拆分，check 按整段覆盖校验。

## 维护（怎么往这个文件里加东西）

只在遇到**清单没覆盖的新失败模式**时更新：先把可泛化的规则提进 SKILL.md，再在日志补一行。一次性站点细节、脚本已自动处理的回退、没实际发生的"差点踩坑"，都不记。

