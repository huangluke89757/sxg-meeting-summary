---
name: sxg-meeting-summary
description: "把会议纪要和逐字原文（PDF/DOCX/TXT）整理成格式严格对齐 WMS 周会标准的 .docx 会议纪要：深拷贝自带母版，红色仿宋大标题、元信息五行、会议目的/核心议题与决策/行动项表格三段式、右对齐落款，不手写任何样式；自动还原发言人真名、从口语推断会议日期与地点、抽取行动项责任人和优先级，并输出待确认清单。当用户说出会议纪要、把这份纪要做成正式文档、按标准格式生成周会纪要、纪要和原文都在整理成 docx、这份会议要出个纪要时使用。"
version: 1.0.0
agent_created: true
---

# 会议纪要生成

把会议材料整理成格式严格对齐 WMS 周会标准的 Word 纪要。格式由自带母版保证：所有段落和表格行都从母版深拷贝后只替换文字，不手写任何样式、不调任何字体字号参数。

## 何时使用

- 用户给出会议纪要（AI 摘要）和/或会议原文（逐字转写），要求输出正式纪要文档。
- 用户要求按 WMS 周会既有格式出纪要。

不触发：只要求口头总结、只要求把已有文档转成其他格式、与会议纪要无关的文档写作。

## 环境检查

生成前按顺序执行，任一步失败按 `references/setup-guide.md` 处理：

1. `python scripts/check_environment.py`：读取 `skill-dependencies.json`，输出 ready / partial / needs_setup / unavailable。
2. `python -c "import docx"`：确认 python-docx 可导入。失败时先安装再继续，不得跳过。

环境未就绪时不得直接生成。

## 流程

### 1. 提取材料

```text
python scripts/extract_input.py <纪要文件> --output <纪要文本路径>
python scripts/extract_input.py <原文文件> --output <原文文本路径> --speakers
```

- 支持 PDF / DOCX / TXT / MD；PDF 依次尝试 pdfplumber、PyPDF2、pymupdf，任一可用即停止。
- `--speakers` 输出 `[mm:ss] 姓名:` 形式的发言人及出现次数，用于把"发言人1/发言人2"还原成真人。
- 原文超长时用 `--max-chars` 分段读取，优先看开头和结尾：开头常出现日期，结尾常出现结论与收尾安排。

### 2. 补齐元信息

从材料中提取会议时间、会议地点、主持人、参会人员、记录人。

- 纪要里通常没有时间地点，去原文找"现在是 X 月 X 号""线上会议""投屏"这类口语线索。
- 参会人员以 `--speakers` 统计为准，按发言次数从多到少排列。
- 主持人取掌控议程、宣布散会的人；记录人取说"我出纪要"的人。
- 推断不出的一律写"待确认"，并列入交付时的待确认清单。禁止用职务或常见人名填充。

### 3. 提炼内容

按 `references/writing-guide.md` 组织成：会议目的 3—5 条、综述 1 段、议题若干（每个含关键结论 + 决策事项）、行动项若干。所有内容必须能在材料里找到出处。

**注意分句上限**：关键结论可用分号并列，但分句 ≤4 个且总字数 ≤150；超出改用「- 」分条，每条一个事实层次。不要为追求公文观感把多层信息压成一句长句。

### 4. 原文反向检索（写 spec 之前必做）

结论只能从原文逐字稿取，不许从 AI 摘要转写。对第 3 步提炼出的每条结论逐项核对：

1. **数量词**（N 次/N 处/全部）：grep 原文计数。
2. **否定与绝对化表述**（不能做/无法实现/不支持）：同时检索该发言人是否给过例外或让步（「可以」「但前提」「除了」）。
3. **方案间关系**：「A 否则 B」多为递进，不是并列。

产出证据表 `主张 | 时间戳 | 原话摘录`，**未能在原文定位的主张不得进入 spec**。规则详见 `references/writing-guide.md` 的同名章节。

### 5. 写 spec.json

在工作目录写 `spec.json`，字段见下表，完整示例见 `assets/spec.example.json`。

| 字段 | 类型 | 说明 |
|---|---|---|
| template | 字符串 | 母版路径；省略则用 skill 自带母版 |
| output | 字符串 | 输出 docx 路径；相对路径按 spec 所在目录解析 |
| overwrite | 布尔 | 目标存在时是否需要覆盖；默认拒绝覆盖 |
| meta | 对象 | time / place / host / attend / recorder |
| purpose | 数组 | 会议目的条目，自带"1."编号前缀 |
| summary | 字符串 | 二、模块下的综述段 |
| topics | 数组 | 每项含 title / conclusion / decision |
| actions | 数组 | 每项含 no / content / owner / priority |
| action_title | 字符串 | 行动项标题，默认「三、 行动项 (Action Items)」 |
| include_supplement | 布尔 | 是否输出「四、 补充说明」，默认关闭 |
| supplement | 字符串 | include_supplement 为真时的正文 |
| sign_date | 字符串 | 落款日期，形如「2026年09月29日」 |

写完 spec 后、生成之前，先跑内容闸：

```text
python scripts/verify_content.py <spec.json>
```

- **FAIL**（确定性可自动判定）：分句 >4、字数 >150、结构缺失、优先级非法、决策事项无责任人。有 FAIL 必须改 spec，不得带着 FAIL 生成。
- **WARN**（需回原文人工核对）：数量词、绝对化表述、方案关系、结论未挂时间戳、元信息待确认。WARN 不阻断，但每一条都要真的回原文核过再交付，并在待确认清单里说明。

### 6. 生成

```text
python scripts/build_minutes.py <spec.json>
```

输出顶层元素数、sections 数和行动项行数。目标文件已存在且未声明 `overwrite` 时脚本直接拒绝并退出码 3，此时改用新文件名或请用户确认。

### 7. 校验（双闸，缺一不可）

```text
python scripts/verify_content.py <spec.json>     # 内容闸：说得对不对、读不读得下去
python scripts/verify_docx.py <生成的.docx>      # 格式闸：像不像一份正式文件
```

- verify_content：FAIL 0 才能生成；WARN 逐条回原文核对。
- verify_docx：校验 A4 与页边距、`sectPr`、标题字体字号颜色、元信息五行、编号段缩进、关键结论缩进、正文字号、表格列宽、落款对齐。必须 0 失败才算完成。

**两道闸不可互相替代**：verify_docx 全绿只保证「像一份正式文件」，不保证「说得对」；verify_content 全绿只保证「没说错、读得下去」，不保证排版合规。只做格式闸不做内容闸，等于把「排版工整的错误结论」交给领导。

### 8. 交付

报告输出路径、元信息五项取值、议题数、行动项数，并单独列出待确认清单（推断出的日期、还原出的人名、模糊的截止时间）。

## 输出规范

- 文件落在源纪要同目录，命名 `WMS周会会议纪要YYYYMMDD.docx`，日期取会议日期。
- 不改动母版和用户的原始材料。
- 不把中间文本留在用户目录；临时文件写系统临时目录。

## 停止条件

- 环境未就绪且无法降级。
- 材料里没有任何可识别的会议内容。
- 输出路径已存在且用户未确认覆盖。
- 校验存在 FAIL 且无法修复。
- 元信息全部无法推断且用户不补充：先交付结构完整的文档并在待确认清单标注，不臆造。

## 质量自查清单

- [ ] 已运行环境检查，python-docx 可导入
- [ ] 所有段落和表格行来自母版深拷贝，没有手写样式
- [ ] 元信息五项齐全，推断项已标注待确认
- [ ] 每个议题的关键结论和决策事项都能在材料里找到出处
- [ ] **已做原文反向检索**：数量词已计数、绝对化表述已查例外、方案关系已辨并列/递进，证据表齐备
- [ ] **关键结论分句 ≤4 且总长 ≤150 字**，超出已改分条
- [ ] **verify_content.py FAIL 0**，WARN 已逐条回原文核对
- [ ] **内容闸 WARN 已逐条回原文核对，未无依据清除**（清词绕开等于放掉失真）
- [ ] **supplement 文本未带「四、 补充说明：」前缀**（脚本已自动加节标题，避免标题重复）
- [ ] **重建前已删除旧 docx**，未因覆盖拒绝（退出码 3）误判成格式闸失败
- [ ] 行动项含责任人和截止时间或优先级
- [ ] verify_docx 0 失败
- [ ] 已向用户列出待确认清单
- [ ] 未覆盖任何已有文件

## 参考

- 格式规格与母版索引：`references/style-spec.md`
- 内容提炼、分句上限、原文反向检索与 spec 运行纪律：`references/writing-guide.md`
- 纪要类任务开工提示词模板（可直接粘用）：`references/kickoff-prompt.md`
- 依赖安装与故障恢复：`references/setup-guide.md`

## 脚本

| 脚本 | 作用 | 退出码 |
|---|---|---|
| `scripts/check_environment.py` | 环境自检 | 0 就绪 |
| `scripts/extract_input.py` | 提取 PDF/DOCX/TXT/MD 文本，`--speakers` 统计发言人 | 0 成功 |
| `scripts/verify_content.py` | **内容闸**：分句/字数/结构/三类断言 | 0 无 FAIL；1 有 FAIL；2 读不了 |
| `scripts/build_minutes.py` | 由 spec.json 生成 docx | 3 = 拒绝覆盖 |
| `scripts/verify_docx.py` | **格式闸**：页面/字体/缩进/表格/落款 | 0 全过；1 有 FAIL；2 读不了 |
