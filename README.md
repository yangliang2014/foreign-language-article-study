# foreign-language-article-study

Turn a foreign-language article into a **self-contained sentence-by-sentence study page** (offline HTML): original sentence on top, Chinese translation / grammar notes / vocabulary underneath, key phrases highlighted, one-click "original text only" toggle, text-to-speech, dark mode, and an auto-generated glossary. Python 3 standard library only.

**Supported languages (11):** English plus the ten most-studied foreign languages for Chinese learners. Language is auto-detected (script detection wins over a mislabeled `<html lang>`); annotations are always in Chinese. Arabic renders right-to-left; Japanese furigana (`<ruby>`) is stripped automatically.

| Code | Language | Playbook | Splitting notes |
|---|---|---|---|
| en | English | — (this file) | `. ! ?` + capitalization |
| ja | Japanese | [`languages/ja.md`](languages/ja.md) | `。！？` end marks; furigana auto-stripped |
| ko | Korean | [`languages/ko.md`](languages/ko.md) | `. ! ?`, case-insensitive |
| fr | French | [`languages/fr.md`](languages/fr.md) | Latin splitting, `« »`, space before `?` |
| de | German | [`languages/de.md`](languages/de.md) | Latin splitting, `z. B.`-style abbreviations, separable verbs |
| es | Spanish | [`languages/es.md`](languages/es.md) | Latin splitting, `¿ ¡` inverted marks |
| ru | Russian | [`languages/ru.md`](languages/ru.md) | Latin splitting, Cyrillic caps & initials |
| it | Italian | [`languages/it.md`](languages/it.md) | Latin splitting, `dott.ssa`-style titles |
| pt | Portuguese | [`languages/pt.md`](languages/pt.md) | Latin splitting, personal infinitive |
| ar | Arabic | [`languages/ar.md`](languages/ar.md) | RTL, `. ! ؟`, Arabic comma doesn't split |
| th | Thai | [`languages/th.md`](languages/th.md) | split on spaces, needs heavy merging |

English | [中文](README.zh-CN.md)

## Install

```bash
git clone git@github.com:yangliang2014/foreign-language-article-study.git
cp -R foreign-language-article-study ~/.claude/skills/article-study
```

Then tell Claude Code "精读 &lt;URL&gt;" (study this article) and it runs the whole pipeline automatically. You can also drive it manually with `python3 article_study.py <command>`. Headless Chrome is used for sites that block curl and for screenshots.

## Usage

```bash
# auto-detects language; force it with --lang en|ja|ko|fr|de|es|ru|it|pt|ar|th
python3 article_study.py prep "<URL>" -d article-output    # fetch + skeleton + draft template
# fill in the generated *.draft.md: zh translation / gr grammar / ph phrases
python3 article_study.py fill   <name>.draft.md -j analysis.json
python3 article_study.py check  <file>.html -j analysis.json   # reports ALL problems at once
python3 article_study.py inject <file>.html -j analysis.json   # run only after check is OK
python3 article_study.py verify <file>.html -j analysis.json
python3 article_study.py shot   <file>.html                    # screenshot shards for review
python3 article_study.py open   <file>.html
```

Each sentence is one block in the draft — fill only zh/gr/ph (the `> en:` line holds the source text in whatever language):

```
# 0.0
> en: Philbrick lays out the goal.   # read-only source sentence
zh: 菲尔布里克阐明了目标。
gr: ｛一般现在时｝；lay out 是｛短语动词｝
ph:
- lays out | 阐明、摆出
hl:
```

- zh / gr are required, ph is optional; wrap grammar terms in full-width `｛｝`.
- **Each ph entry must be a verbatim span from the sentence** (conjugated/inflected form as it appears, never the dictionary form, no `sb/sth` placeholders). Leave hl empty to auto-highlight all ph entries.
- Sentence boundaries can be fixed directly in the draft (split or merge blocks).
- **Read the per-language playbook before filling a non-English draft** — sources, sentence-splitting quirks, grammar-term packs, and ph examples live in [`languages/`](languages/): e.g. Thai is split on spaces and needs heavy merging, Arabic splits on `. ! ؟` with RTL layout.

## Troubleshooting

- prep warns about HTML entities → rerun with `--normalize`.
- check says "highlight phrase not found" → the ph entry is a dictionary form; replace it with the exact form used in the sentence.
- check says "sentence not found in paragraph" → see [SKILL.md](SKILL.md) section 2 for the concatenation-diff method.
- Japanese/Arabic/Thai glyphs look odd in screenshot previews → a downscaling artifact; review native-resolution shards only.

Full rules: [SKILL.md](SKILL.md) · language playbooks: [`languages/`](languages/) · failure log: [issues.md](issues.md) · real example: `example-analysis.json`.
