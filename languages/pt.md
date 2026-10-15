# 葡萄牙语（pt）精读 playbook（巴西葡语为主，profile bcp47 为 pt-BR）

填 draft 前读本文件。通用流程见 [../SKILL.md](../SKILL.md)；本文件只说葡语特有的坑。

## 信源与拓文

- 巴西：**G1**（g1.globo.com，免费、量大、句式新闻规范）、Folha de S.Paulo（付费墙，JSON-LD 兜底）、UOL、BBC Brasil、VOA Português.
- 欧洲葡语：RTP Notícias（rtp.pt/noticias）、Público（付费墙）、Observador.
- 学习信源：Practice Portuguese（欧洲葡语音频+文稿）、Street Smart Brazil（巴西，短文带词汇）、FFLCH 各大学的分级阅读 PDF（多为时政短文）。
- 直接 `prep --lang pt "<URL>"`；系统拉丁字体栈。默认语音 `pt-BR`；欧葡文章也能用，只是朗读带巴西音。

## 断句

- `. ! ?` + 空白 + 大写断；缩写表含 Sr./Sra./Dr./Dra./prof./p./pág./vol./num/nr./ex. 及月份 jan/fev/mar/abr/mai/jun/jul/ago/set/out/nov/dez。
- 数字千位用点小数逗号（`3.000`/`3,14`）；和其他拉丁语言同。
- 葡语代词常以连字符附着（`disse-lhe`、`fazê-lo`），是连续片段，不影响断句。
- 欧式葡语偶尔使用中缀语序（`dar-lhe-ei` 中缀代词），整块连续，直接照抄。
- MSA 风格长句在 G1 常见，骨架偶有"一句套两个主句"——按通用规则在 draft 手动拆句。

## 填 draft（zh / gr / ph / hl）

### gr：用 `｛｝` 标葡语语法点

常用包：
`｛陈述式现在时｝`、`｛简单过去时 perfeito｝`、`｛未完成过去时 imperfeito｝`、`｛过去未完成屡发｝`、`｛现在完成时/屡发 perfeito composto｝`、`｛将来时｝`、`｛条件式｝`、
`｛虚拟式现在时｝`、`｛虚拟式未完成时｝`、`｛虚拟式未来时（葡特有）｝`、`｛命令式｝`、`｛人称不定式 infinitivo pessoal（葡特有）｝`、
`｛冠词与名词性数｝`、`｛缩合 do/da/no/na/ao/à/pelo/pela｝`、`｛指示代词｝`、`｛非重读宾格代词 o/a/lhe/me｝`、
`｛自反/被动 se｝`、`｛无人称 se｝`、`｛ser/estar｝、｛ter/haver｝`、`｛关系代词 que/onde/cujo｝`、
`｛比较级 mais/menos/tão…quanto｝`、`｛最高级｝`、`｛副动词/分词｝`、`｛使役 deixar/fazer+inf.｝`、`｛crase à/às｝`。

### ph：写实际形态，缩合与附着代词整段收

- 对：`foi embora`、`tem feito`、`disse-lhe`（欧式附着）、`me disse`（巴西前置）、`à noite`（crase）、`pelo contrário`、`daqui a pouco`、`está com fome`
- 错：`ir embora`、`ter feito`（原形组合）、`V algo`、`disse-lhe` 的词典写法 `dizer lhe`
- crase `à/às` 与缩合词（`do = de+o`、`noutro`）整段是最小连续单位，别拆开收。
- 巴西葡语代词可置动词前（`ele me disse`），欧葡多后置（`disse-me`），照句中实际词序写。

### zh

葡语"人称不定式"（带人称词尾的不定式：para eu fazer）中文按普通目的/主语小句译即可；虚拟式未来时（quando eu for）译"等我去……时"。

## 朗读与字体

- 朗读 `pt-BR`；系统拉丁字体栈。
- 重音符号 ã/õ/ç/â/ê/é/í/ó/ú 全部照抄、大小写敏感。

## 非目标

- 欧葡/巴葡拼写（CCP 前差异）与发音对比不展开，按文章实际拼写讲。
- 中缀代词（中置位）语法争议点到为止。
