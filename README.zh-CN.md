# foreign-language-article-study

把外文文章变成**离线逐句精读 HTML**：上为外文原句，下为 中文译文 / 语法 / 短语 对照，重点短语高亮，一键切「只看原文」，支持朗读、深色模式与自动词汇表。仅依赖 Python 3 标准库。

**支持语言（11 种）：** 英语 + 中国学生最常学的十门外语。语言自动识别（文种探测优先于错标的 `<html lang>`）；注释始终为中文。阿拉伯语成品自动 RTL 排版；日语 `<ruby>` 注音自动剥除。

| 语码 | 语言 | playbook | 断句特点 |
|---|---|---|---|
| en | 英语 | —（本文件） | `. ! ?` + 大写 |
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

[English](README.md) | 中文

## 安装

```bash
git clone git@github.com:yangliang2014/foreign-language-article-study.git
cp -R foreign-language-article-study ~/.claude/skills/article-study
```

之后对 Claude Code 说「精读 &lt;URL&gt;」即可自动走完全流程。也可直接 `python3 article_study.py <命令>` 手工使用。headless Chrome 用于抓取被拦截的站点和截图。

## 使用

```bash
# 自动识别语言；可用 --lang en|ja|ko|fr|de|es|ru|it|pt|ar|th 强制指定
python3 article_study.py prep "<URL>" -d article-output    # 抓取 + 骨架 + draft 模板
# 填写生成的 *.draft.md：zh 译文 / gr 语法 / ph 短语
python3 article_study.py fill   <名>.draft.md -j analysis.json
python3 article_study.py check  <file>.html -j analysis.json   # 一次列出全部问题
python3 article_study.py inject <file>.html -j analysis.json   # check OK 后注入
python3 article_study.py verify <file>.html -j analysis.json
python3 article_study.py shot   <file>.html                    # 截图分片核对
python3 article_study.py open   <file>.html
```

draft 每句一块，只填 zh/gr/ph（`> en:` 行只读，装该语言原文）：

```
# 0.0
> en: Philbrick lays out the goal.   # 只读原句
zh: 菲尔布里克阐明了目标。
gr: ｛一般现在时｝；lay out 是｛短语动词｝
ph:
- lays out | 阐明、摆出
hl:
```

- zh / gr 必填，ph 可空；语法术语用全角 `｛｝` 包裹。
- **ph 英文列必须是句中逐字片段**：写 `lays out`、`Rather than`，不写词典原形 `lay out`，禁用 `sb/sth`；hl 留空即自动高亮 ph。
- 断句边界可直接在 draft 里修（拆分 / 合并块）。
- **填非英语 draft 前先读对应语言 playbook** —— 信源、断句坑、语法术语包、ph 正反例都在 [`languages/`](languages/)：如泰语按空格切分需大量合句，阿拉伯语按 `. ! ؟` 断句且成品 RTL。

## 排错

- prep 报 HTML 实体 → 加 `--normalize` 重跑。
- check 报「高亮找不到」→ ph 写成了词典原形，按清单改成句中形式。
- check 报「段落中找不到句子」→ 见 [SKILL.md](SKILL.md) 第 2 节拼接 diff 定位。
- 日 / 阿 / 泰字符在截图预览里发虚 → 缩放伪影，只看原生分辨率分片。

完整规则见 [SKILL.md](SKILL.md) · 语言 playbook 见 [`languages/`](languages/) · 故障清单见 [issues.md](issues.md) · 真实范例见 `example-analysis.json`。
