# 依赖安装与故障恢复

本 skill 只用本地 Python 环境，不联网、不登录、不需要任何凭据。

## python-runtime（Python 运行时）

依赖标识 python-runtime。

- 用途：运行全部脚本。
- 最低版本：3.10。
- 官方主页：https://www.python.org/
- 官方文档：https://docs.python.org/3/
- 下载地址：https://www.python.org/downloads/
- 验证：`python --version`

Windows 上优先使用隔离虚拟环境，避免在用户环境里全局安装：

```text
python -m venv <venv 路径>
<venv 路径>/Scripts/python.exe -m pip install python-docx pdfplumber
```

## python-docx（必需）

- 用途：读取母版、生成 docx、校验格式。缺失时无法生成。
- 官方主页：https://github.com/python-openxml/python-docx
- 官方文档：https://python-docx.readthedocs.io/en/latest/
- 安装：`pip install python-docx`
- 验证：`python -c "import docx; print(docx.__version__ if hasattr(docx,'__version__') else 'ok')"`
- 故障恢复：安装后仍无法导入，检查 `pip` 与运行 `python` 是否同一环境；用 `python -m pip install python-docx` 强制装到当前解释器。
- 版本兼容性：1.x 均可；低于 0.8 不支持部分表格接口。

降级：python-docx 不可用时停止生成，先输出结构化 spec.json 和内容文本，标注"文件未生成"，不允许用手写样式或其他库替代母版克隆。

## pdf-extractor（PDF 提取库，可选）

依赖标识 pdf-extractor。三个引擎任意可用即可，脚本按 pdfplumber → PyPDF2 → pymupdf 顺序自动降级。

官方文档：https://github.com/jsvine/pdfplumber#readme

| 引擎 | 安装 | 官方主页 |
|---|---|---|
| pdfplumber | `pip install pdfplumber` | https://github.com/jsvine/pdfplumber |
| PyPDF2 | `pip install PyPDF2` | https://github.com/py-pdf/PyPDF2 |
| pymupdf | `pip install pymupdf` | https://pymupdf.readthedocs.io/ |

- 验证：`python -c "import pdfplumber"`
- 故障恢复：三者都缺时，请用户把 PDF 另存为 TXT 或 DOCX，再重新提取；`extract_input.py` 原生支持这两种格式。
- 扫描件 PDF 没有文本层，三个引擎都提取不出内容：请用户提供带文本层的版本或先做 OCR，此时标注"未验证"。

## 输出目录写权限（必需）

- 用途：写入生成的 docx。
- 验证：`python -c "import os;print(os.access(r'<输出目录>', os.W_OK))"`
- 故障恢复：目标目录只读时改用用户主目录或临时目录，并在交付时说明实际落点；不要尝试提权。

## 环境状态路由

| 状态 | 处理 |
|---|---|
| ready | 直接生成，不展示任何安装步骤 |
| partial | PDF 引擎缺失时仍可生成，只要材料是 TXT/DOCX 或用户提供文本 |
| needs_setup | python-docx 缺失时只展示它的安装与验证步骤，装完重跑检查 |
| unavailable | 输出目录不可写时换落点；全部 PDF 引擎不可用时转 TXT/DOCX |

## 功能降级矩阵

| 功能 | 触发条件 | 降级方式 | 需要用户补充 | 限制 | 恢复 | 停止条件 |
|---|---|---|---|---|---|---|
| 提取 PDF 材料 | 三个 PDF 引擎都不可用 | 改用 TXT/DOCX 输入 | 另存的文本或 Word 文件 | 扫描件无法处理 | 安装任一 PDF 引擎 | 必须解析扫描件且用户无法提供文本 |
| 生成 docx | python-docx 缺失 | 输出 spec.json 与纯文本内容，标注文件未生成 | 无 | 无格式化产物 | 安装 python-docx 后重跑 | 用户必须当场拿到 docx |
| 写入目标目录 | 目录只读或已存在同名文件 | 换落点或改用新文件名 | 确认新路径 | 落点与原计划不同 | 取得写权限 | 用户坚持覆盖且未确认 |
| 格式校验 | 输出文件无法打开 | 只做静态检查，标记未完成运行验证 | 无 | 不得给出通过结论 | 修复文件后重跑 | 需正式验收结论 |
