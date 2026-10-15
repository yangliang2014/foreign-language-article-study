# 西班牙语（es）精读 playbook

填 draft 前读本文件。通用流程见 [../SKILL.md](../SKILL.md)；本文件只说西语特有的坑。

## 信源与取文

- 普通新闻：RTVE（rtve.es，免费规范）、BBC Mundo、El País（软付费墙，JSON-LD 兜底）、Reuters Spanish、VOA Español.
- 学习信源：Instituto Cervantes 的 **PracticaEspañol**（practicaespanol.com，新闻按 B1/B2 分级带练习与音频）、News in Slow Spanish（新闻改写）、VeinteMundos（拉美生活短文）。
- 直接 `prep --lang es "<URL>"`；系统拉丁字体栈。
- 西班牙与拉美的用词/时态差异（coche/carro、vosotros/ustedes）在 zh 里取上下文义，不另注。

## 断句

- `. ! ?` + 空白 + 大写断；缩写表含 Sr./Sra./Srta./Dr./Dra./prof./p./pág./vol./no./cf./v.gr./EE. UU.（带空格与不带空格两种写法都处理）及月份。
- **倒装问号/叹号 `¿ … ?`、`¡ … !`**：开符号（¿ ¡）不触发断句，闭符号正常断；句子的 `> en:` 必须连开符号一起照抄。
- 数字千位用点（`3.000`）、小数用逗号（`3,14`）；数字+点+数字识别为千位/小数不断。
- 问句常见 `?` 前无空格的排版也能正确断（`?` 后要求空格+大写）。
- 西语人名带两个姓氏、地名带连写（Nueva York）不影响。

## 填 draft（zh / gr / ph / hl）

### gr：用 `｛｝` 标西语语法点

常用包：
`｛陈述式现在时｝`、`｛简单过去时 indefinido｝`、`｛未完成过去时 imperfecto｝`、`｛现在完成时 perfecto｝`、`｛过去完成时 pluscuamperfecto｝`、`｛将来时｝`、`｛条件式｝`、
`｛虚拟式现在时 subjuntivo｝`、`｛虚拟式未完成时｝`、`｛命令式 afirmativo/negativo｝`、
`｛ser/estar｝`、`｛por/para｝`、`｛非重读物主/宾与格代词 lo/le/se｝`、`｛与格替代 leísmo 现象｝`、
`｛双宾语代词 me lo｝`、`｛自复/自被动 se｝`、`｛无人称 se｝`、`｛原形动词 al+inf.｝`、
`｛短语动词 ir a / volver a / soler / acabar de / dejar de｝`、`｛进行时 estar+副动词｝`、
`｛比较级 más/menos/mayor/menor｝`、`｛最高级 -ísimo｝`、`｛关系代词 que/donde/cuyo/quien｝`、
`｛tener que / hay que｝`、`｛llevar+时间｝`、`｛se 意外事件句｝`、`｛感叹句 qué/cuánto｝`。

### ph：写实际变位形态，连写代词整段照抄

- 对：`he dicho`、`se dio cuenta de`、`se levanta`、`levantándose`（副动词带代词）、`dámelo`（命令式附双代词）、`hay que salir`、`hace tres días`、`tan ... como` 取连续半边
- 错：`decir`、`darse cuenta`（辞书形）、`levantarse`（未体现句中附着）、`algo/alguien` 占位
- 代词附在变位动词后连写时（`díselo`、`verlo`）整段是一个连续片段，ph 直接收整段；
- 否定/代词插在中间的短语（`no lo sé`）整段连续可收；`ir a + inf.` 两词常被其他词隔开时只收连续部分。

### zh

简单过去时（一次性、有界）译"了"，未完成过去时（背景、惯常、持续）译"当时在/过去常常"；虚拟式大多不直译，用"希望/要/也许"体现。

## 朗读与字体

- 朗读 `es-ES`；系统拉丁字体栈。
- 重音符号 `á é í ó ú ñ ü ¿ ¡` 全部大小写敏感照抄。

## 非目标

- 虚拟式各触发词的完整清单不展开，按句中实际触发点标注。
- 拉美 voseo（vos）规则不单独讲，遇到照实际形态讲。
