# 法语（fr）精读 playbook

填 draft 前读本文件。通用流程取文/三路上报/覆盖校验跨语言相同，见 [../SKILL.md](../SKILL.md)；本文件只说法语特有的坑。

## 信源与取文

- 首选学习信源：**TV5MONDE apprendre**（apprendre.tv5monde.com）——按 A1~B2 分级新闻，句式规范；**RFI 简易法语**（rfi.fr 搜 "journal en français facile"）——新闻句式简化、常附音频。
- 普通新闻：Le Monde（付费墙，skill 自动走 JSON-LD 兜底取全文）、France 24（france24.com/fr/）、RFI、Libération、Les Échos.
- 直接 `prep --lang fr "<URL>"`；系统字体即可，无特殊字体栈。
- 法语标题常不大写、句末带问号/句号；h1 若分析则在 draft 保留，否则整块删除规则不变。

## 断句

- 正常 `. ! ?` + 空白 + 大写断；缩写表已含 M./Mme/Mlle./dr./pr./cf./p./vol./no. 及月份缩写 janv./févr./avr./juil./sept./oct./nov./déc.
- **问号/叹号/冒号前有空格是正常排版**（`Tu vas où ?`、`Voici : …`），不影响断句；骨架在 `?` + 空格 + 大写处断。
- 尖括号引号 `« … »` 已处理：`« Bonjour. »` 式（句号与闭书名号间有空格）正确断在 » 之后。
- 数字千位用空格（`3 000`），句中没有句点，不会误断；小数用逗号（`3,14`）同理。
- 省文撇用弯撇 `’`（`l’école`、`qu’il`）——**ph/hl 必须照抄弯撇**（校验会与弯撇归一为直撇，但注释放大看仍建议照源文写）。
- 多词缩写（`p. ex.`、`s. v. p.`）若误断，在 draft 合句；脚本已处理单字母+空格+大写点（`qqch.` 之类罕见）。

## 填 draft（zh / gr / ph / hl）

### gr：用 `｛｝` 标法语语法点

常用包：
`｛直陈式现在时 présent｝`、`｛复合过去时 passé composé｝`、`｛未完成过去时 imparfait｝`、`｛愈过去时 plus-que-parfait｝`、`｛简单将来时 futur simple｝`、`｛先将来时 futur antérieur｝`、`｛条件式 conditionnel｝`、`｛虚拟式 subjonctif｝`、
`｛最近过去时 venir de｝`、`｛最近将来时 aller｝`、`｛进行时 être en train de｝`、
`｛代词作前置宾语 COD/COI｝`、`｛副代词 y｝`、`｛副代词 en｝`、`｛重读代词 moi/lui/eux｝`、
`｛关系代词 qui/que/où/dont｝`、`｛ce qui/ce que 无先行词｝`、`｛缩合冠词 au/du/aux/des｝`、`｛部分冠词 du/de la/des｝`、
`｛否定 ne…pas/plus/jamais/personne/rien｝`、`｛限定 ne…que｝`、`｛命令式 impératif｝`、`｛副动词 en+现在分词｝`、
`｛使役结构 faire faire｝`、`｛感官动词 voir/entendre+inf.｝`、`｛强调 c’est…que/qui｝`、`｛si 条件三式｝`、
`｛疑问倒装/est-ce que｝`、`｛过去分词性数配合｝`、`｛代词式动词 se｝`、`｛无人称 il y a/il faut｝`。

### ph：写句中实际形态，不要写不定式

- 对：`s'est levé`（自反+复合过去时实际形态）、`ont l'habitude de`、`n'est pas`、`faut partir`、`vient de partir`、`allons-y`
- 错：`se lever`、`avoir l'habitude de`（不定式/泛时形态）、`ne...pas`（不连续）、`qch`、`qn`

否定结构在句中经常不连续（`ne ... jamais`）——ph 写连续半边（`n'ai jamais` 若中间无插入则连续；被代词隔开时只写最值得讲的片段），需要跨成分时用 hl 写长片段。
省音片段照抄：`qu'il`、`l'école`、`c'est`、`s'il`。

### zh

部分冠词常不译（`du pain`＝些面包/面包）；虚拟式用"要/得/也许"体现语气即可，不要一律译"竟然"。y/en 指代要回上文补出具体名词。

## 朗读与字体

- 朗读 `fr-FR`；系统拉丁字体栈，无特殊字体。
- 法语连读/联诵（enchaînement）TTS 自动处理；逐句精读块只显示文字。

## 非目标

- 尾音 e caduc、联诵必选/禁用规则不展开。
- 魁北克/比利时变体拼写差异不标注。
