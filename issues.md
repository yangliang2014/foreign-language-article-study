# issues.md — 精读踩坑诊断

写 draft 和截图核对前过一遍下面的**故障信号**。规则与修法在 SKILL.md（唯一出处），这里只列信号本身和定位线索。

## 故障信号

- 短语/词汇表显示成字面 **`en — zh`** 或方框 → ph 写成了 dict 对象；draft 流程从语法上杜绝，手写 JSON 才会发生，verify 必拦。
- verify FAIL **`&amp;#…` 双重转义**，或 skeleton 打印 **实体警告** → 源文正文残留 HTML 实体，修法见 SKILL.md「实体体检分支」。
- 某句读着是两句话却只有一个编号（典型：`…,” sb said/wrote on X. Surprisingly/And …`）→ skeleton 漏断，在 draft 同一块内加一组 `> en:`。
- check 连续报「高亮短语在句中找不到」、ph 看着却"没错"（`lay out`、`put ... in perspective`、带 `sb/sth`）→ ph 写了词典原形而非句中逐字片段；规则见 SKILL.md 第 2 步，check 会一次列全所有不命中。
- check 报「段落中找不到句子」、实体也已归一过 → 骨架 `> en:` 句尾带了正文容器里不存在的字符；定位法见 SKILL.md 第 2 步。
- 想 Read 全页截图核对 → 停，只读 `<名>.parts/` 分片（原因见 SKILL.md 第 4 节）。

## 日志（最新在前，一行：站点 — 症状 → 现在由什么兜住）

- 2026-10-15 · 脚本改进（NatGeo 篇返工耗时）— check 每轮只报第一个 hl，88 条错误要跑很多轮 → `validate_analysis` 渲染前聚合校验，一次列出字段/覆盖/全部 hl 错误。
- 2026-10-15 · National Geographic《Philbrick 淘金热访谈》— 子代理填的 ph 全是词典原形/`sb/sth` 模式，88 条高亮不命中，check 每次只报一条 → SKILL.md 第 2 步 ph 逐字规则 + 第 3 步 fill 前全量子串审计。
- 2026-10-15 · 同篇 — check 报第 8 段找不到句子，`--normalize` 后仍失败（断句取 JSON-LD、正文取 DOM，句尾 `.”` 只存于前者）→ SKILL.md 第 2 步拼接 diff 定位、改 draft 的 `> en:`。
- 2026-10-15 · New Scientist《dumped 722 maths papers》— 精读块出现字面 `doesn&#x27;t`，check 与原文模式都正常 → skeleton 实体体检 + `--normalize`，verify 兜底。
- 2026-10-15 · 同篇 — ph 写成 dict，check 通过但全篇渲染成 `en — zh` → draft DSL 语法杜绝 + verify 断言。
- 2026-10-15 · 同篇 — 末段 `…he wrote on X. Surprisingly…` 并成一句 → draft 块内加 `> en:` 拆分，check 按整段覆盖校验。

## 维护（怎么往这个文件里加东西）

只在遇到**清单没覆盖的新失败模式**时更新：先把可泛化的规则提进 SKILL.md，再在日志补一行。一次性站点细节、脚本已自动处理的回退、没实际发生的"差点踩坑"，都不记。

