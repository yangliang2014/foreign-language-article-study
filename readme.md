# english-article-study

把英文文章变成**离线逐句精读 HTML**：英文原句 + 中文译文 / 语法 / 短语对照，重点短语高亮，一键切「只看原文」，支持深色模式与自动词汇表。仅依赖 Python 3 标准库。

## 安装

```bash
git clone git@github.com:yangliang2014/english-article-study.git
cp -R english-article-study ~/.claude/skills/article-study
```

之后对 Claude Code 说「精读 &lt;URL&gt;」即可自动走完全流程。也可直接 `python3 article_study.py <命令>` 手工使用。headless Chrome 用于抓取被拦截的站点和截图。

## 使用

```bash
python3 article_study.py prep "<URL>" -d article-output    # 抓取 + 骨架 + draft 模板
# 填写生成的 *.draft.md：zh 译文 / gr 语法 / ph 短语
python3 article_study.py fill   <名>.draft.md -j analysis.json
python3 article_study.py check  <file>.html -j analysis.json   # 一次列出全部问题
python3 article_study.py inject <file>.html -j analysis.json   # check OK 后注入
python3 article_study.py verify <file>.html -j analysis.json
python3 article_study.py shot   <file>.html                    # 截图分片核对
python3 article_study.py open   <file>.html
```

draft 每句一块，只填 zh/gr/ph：

```
# 0.0
> en: Philbrick lays out the goal.   # 只读，勿改
zh: 菲尔布里克阐明了目标。
gr: ｛一般现在时｝；lay out 是｛短语动词｝
ph:
- lays out | 阐明、摆出
hl:
```

- zh / gr 必填，ph 可空；语法术语用全角 `｛｝` 包裹。
- **ph 英文列必须是句中逐字片段**：写 `lays out`、`Rather than`，不写词典原形 `lay out`，禁用 `sb/sth`；hl 留空即自动高亮 ph。

## 排错

- prep 报 HTML 实体 → 加 `--normalize` 重跑。
- check 报「高亮找不到」→ ph 写成了词典原形，按清单改成句中形式。
- check 报「段落中找不到句子」→ 见 [SKILL.md](SKILL.md) 第 2 节拼接 diff 定位。

完整规则见 [SKILL.md](SKILL.md)，故障清单见 [issues.md](issues.md)，真实范例见 `example-analysis.json`。
