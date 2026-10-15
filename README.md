# english-article-study

Turn an English article into a **self-contained sentence-by-sentence study page** (offline HTML): original sentence on top, Chinese translation / grammar notes / vocabulary underneath, key phrases highlighted, one-click "original text only" toggle, dark mode, and an auto-generated glossary. Python 3 standard library only.

English | [中文](README.zh-CN.md)

## Install

```bash
git clone git@github.com:yangliang2014/english-article-study.git
cp -R english-article-study ~/.claude/skills/article-study
```

Then tell Claude Code "精读 &lt;URL&gt;" (study this article) and it runs the whole pipeline automatically. You can also drive it manually with `python3 article_study.py <command>`. Headless Chrome is used for sites that block curl and for screenshots.

## Usage

```bash
python3 article_study.py prep "<URL>" -d article-output    # fetch + skeleton + draft template
# fill in the generated *.draft.md: zh translation / gr grammar / ph phrases
python3 article_study.py fill   <name>.draft.md -j analysis.json
python3 article_study.py check  <file>.html -j analysis.json   # reports ALL problems at once
python3 article_study.py inject <file>.html -j analysis.json   # run only after check is OK
python3 article_study.py verify <file>.html -j analysis.json
python3 article_study.py shot   <file>.html                    # screenshot shards for review
python3 article_study.py open   <file>.html
```

Each sentence is one block in the draft — fill only zh/gr/ph:

```
# 0.0
> en: Philbrick lays out the goal.   # read-only
zh: 菲尔布里克阐明了目标。
gr: ｛一般现在时｝；lay out 是｛短语动词｝
ph:
- lays out | 阐明、摆出
hl:
```

- zh / gr are required, ph is optional; wrap grammar terms in full-width `｛｝`.
- **Each ph entry must be a verbatim span from the sentence**: write `lays out` / `Rather than`, never the dictionary form `lay out`, no `sb/sth` placeholders. Leave hl empty to auto-highlight all ph entries.

## Troubleshooting

- prep warns about HTML entities → rerun with `--normalize`.
- check says "highlight phrase not found" → the ph entry is a dictionary form; replace it with the exact form used in the sentence.
- check says "sentence not found in paragraph" → see [SKILL.md](SKILL.md) section 2 for the concatenation-diff method.

Full rules: [SKILL.md](SKILL.md) · failure log: [issues.md](issues.md) · real example: `example-analysis.json`.
