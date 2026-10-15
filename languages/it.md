# 意大利语（it）精读 playbook

填 draft 前读本文件。通用流程见 [../SKILL.md](../SKILL.md)；本文件只说意语特有的坑。

## 信源与取文

- 普通新闻：ANSA（ansa.it，免费、句式紧凑）、Rai News（rainews.it）、Il Post（ilpost.it，长篇解释性报道、付费墙很轻）、la Repubblica / Corriere（有阅读条数限制，JSON-LD 兜底）。
- 学习信源：**Online Italian Club**（onlineitalianclub.com，免费分级新闻带音频与词条）、One World Italiano 阅读栏；马可波罗/图兰朵计划语言生可优先用 CELI/CILS 阅读题改写文本。
- 直接 `prep --lang it "<URL>"`；系统拉丁字体栈。

## 断句

- `. ! ?` + 空白 + 大写断；缩写表含 sig./dott./prof./p./pp./vol./no./ecc./cfr./on./avv./ing./arch. 及月份 feb/mar/apr/lug/set/ott/nov/dic。
- **尊称头衔合成词**：`dott.ssa`、`dott.ssa Bianchi` 只有一个内部点（dott.ssa），点前 token 是 dott 命中缩写，不断；同理 `sig.na`。
- 省文撇：`l'Italia`、`un'amica`、`d'accordo`——撇后元音结构照抄；弯撇会归一为直撇比对。
- 数字千位用点（`3.000`）小数逗号（`3,14`）；同西语。
- 感叹常用叠标点（`Dai!`、`Ma che dici?!`）按各自规则断，必要时 draft 合句。

## 填 draft（zh / gr / ph / hl）

### gr：用 `｛｝` 标意语语法点

常用包：
`｛直陈式现在时｝`、`｛近过去时 passato prossimo（essere/avere）｝`、`｛未完成过去时 imperfetto｝`、`｛远过去时 remoto｝`、`｛愈过去时｝`、`｛简单将来时｝`、`｛条件式｝`、
`｛虚拟式 congiuntivo｝`、`｛命令式｝`、`｛副动词 gerundio + stare｝`、
`｛定/不定冠词｝`、`｛缩合前置词 del/nella/sul｝`、`｛组合代词 me lo/dammelo｝`、
`｛直宾代词 lo/la/li/le｝`、`｛间宾 gli/le｝`、`｛小品词 ci｝`、`｛小品词 ne｝`、`｛自反 si｝`、`｛无人称 si｝`、
`｛关系代词 che/cui/dove/il quale｝`、`｛比较级 più/meno…che/di｝`、`｛最高级 -issimo｝`、
`｛piacere 与格主语｝`、`｛servire/volerci/bastare｝`、`｛使役 fare+inf.｝`、`｛过去分词性数配合｝`、`｛强调 è…che｝`。

### ph：写实际形态，注意缩合与组合代词

- 对：`sono andato`、`mi piace`/`mi piacciono`（数随真正主语）、`gliel'ho detto`、`dammelo`、`c'è`/`ci sono`、`in centro`、`di nuovo`、`a causa di` 句中形态
- 错：`andare`、`piacere`（原形）、`avere+participio` 占位、`qlcs/uno`
- 缩合前置词整体收：`dell'acqua`、`nella casa`、`sul tavolo`——它们是连续片段。
- 组合代词附着（`darglielo`、`andarsene`）整段收，gr 里拆讲 ci/ne/与格。

### zh

近过去时与未完成过去时的分工同西语（一次性 vs 背景/惯常）；piacere 类动词要把逻辑宾语翻成主语（"音乐使我喜欢"→"我喜欢音乐"）。

## 朗读与字体

- 朗读 `it-IT`；系统拉丁字体栈。
- 重音尖音符/钝音符（é/è、ó/ò）照抄，句末 `è`（是）与 `e`（和）是不同词。

## 非目标

- 虚拟式在口语中的消亡等语域讨论不展开。
- 远过去时南北使用差异点到为止。
