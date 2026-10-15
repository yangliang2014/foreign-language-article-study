# 德语（de）精读 playbook

填 draft 前读本文件。通用流程见 [../SKILL.md](../SKILL.md)；本文件只说德语特有的坑。

## 信源与取文

- 首选学习信源：**DW Learn German**（learner.dw.com）——Top-Thema（B1，附慢速音频与词汇表）、Langsam gesprochene Nachrichten（B2，慢速新闻逐句稿），是最适合精读书写的德语信源。
- 普通新闻：tagesschau.de（ARD，免费、句式规范）、ZDF/heute、NDR；Die Zeit/Spiegel 有付费墙（自动走 JSON-LD 兜底）。
- 直接 `prep --lang de "<URL>"`；系统拉丁字体栈。
- 德语名词**句中也大写**，复制 ph/hl 时大小写必须逐字照源文（校验大小写敏感）。
- 德语引号是 `„…“`（下开上闭），闭引号是 `“`，脚本已能在 `.“` 后正确断句。

## 断句

- `. ! ?` + 空白 + 大写断；缩写表已含 bzw./ca./nr./zzgl./inkl./evtl./ggf./vgl./hr./fr. 与月份 jan/feb/mär/apr/jun/jul/aug/sep/okt/nov/dez。
- **带空格的分段缩写已处理**：`z. B.`、`d. h.`、`u. a.`、`u. Ä.`、`o. Ä.` 不会误断。
- 数字千位用点（`3.000`）、小数用逗号（`3,14`）——纯数字+点+数字识别为小数不断；但 `25. Oktober` 这种日期（点后空格+大写）**会被当作句末**，若误断在 draft 合句。
- 可分动词的前缀在句末（`Ich stehe um 7 Uhr auf.`），与断句无关，但影响高亮（见下）。

## 填 draft（zh / gr / ph / hl）

### gr：用 `｛｝` 标德语语法点

常用包：
`｛现在时 Präsens｝`、`｛过去时 Präteritum｝`、`｛完成时 Perfekt（haben/sein）｝`、`｛过去完成时 Plusquamperfekt｝`、`｛第一将来时 Futur I｝`、
`｛第二虚拟式 Konjunktiv II｝`、`｛第一虚拟式 Konjunktiv I（间接引语）｝`、
`｛第四格 Akkusativ｝`、`｛第三格 Dativ｝`、`｛第二格 Genitiv｝`、`｛双支配动词｝`、`｛静三动四 Wechselpräpositionen｝`、
`｛可分动词｝`、`｛不可分动词｝`、`｛反身动词 sich｝`、`｛被动 werden-Passiv｝`、`｛状态被动 sein-Passiv｝`、
`｛尾语序 dass/weil 从句｝`、`｛关系从句 Relativsatz｝`、`｛zu+Infinitiv 不定式｝`、`｛um…zu/damit 目的｝`、
`｛als/wenn 时间｝`、`｛ob 疑问从句｝`、`｛形容词词尾变化｝`、`｛比较级/最高级｝`、`｛命令式｝`、`｛介词支配｝`。

### ph：写句中实际形态；可分动词是最大的坑

规则同其他语言：**必须逐字连续、写实际变位**。

- 对：`bin gegangen`、`hat ... gemacht`（中间无插入才连续）、`muss arbeiten`、`im Dezember`（=in dem）、`zur Schule`（=zu der）、`sich freuen auf` 的实际片段 `freut sich auf`
- 错：`gehen`、`gemacht haben`（不定式结构）、`sich freuen`（辞书形）、`etw./jmdm.`（占位符）

**可分动词的两段不连续**（`Ich rufe dich später an.` 中 `rufe … an`）：不能写一个跨越插入成分的 ph。
- 只讲动词义时，ph 写动词在句中的连续部分（如 `rufe` 或句末 `an`），释义说明"anrufen 打电话，可分前缀 an 后置"；
- 确需把整句框架作为重点时，用 `hl` 也只能写连续片段，分别高亮 `rufe` 和 `an`（用 ` | ` 分两条）；
- **跨片段的单个高亮（DSL 扩展）暂不支持**，不要发明语法。

### zh

框架结构（框形结构：变位动词第二位、可分前缀/过去分词/不定式压句末）在翻译上无对应，zh 正常顺译；gr 里点明框架即可。虚词 aber/denn/und/oder/sondern 不占框。

## 朗读与字体

- 朗读 `de-DE`；系统拉丁字体栈。
- 变音 `ä ö ü ß` 照抄（hl 大小写与变音敏感）；`ß` 与 `ss` 是不同字符。

## 非目标

- 各地区（德/奥/瑞）用词差异不标注。
- 可分/不可分同形动词（unterhalten 两义）的深层辨析点到为止。
