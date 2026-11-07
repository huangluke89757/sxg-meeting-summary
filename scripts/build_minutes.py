# -*- coding: utf-8 -*-
"""会议纪要生成器：spec.json + 母版 docx -> 同格式会议纪要 docx。

用法：
    python build_minutes.py <spec.json>

spec.json 字段见 assets/spec.example.json。
所有段落和表格行都从母版深拷贝后只替换文字，不手写任何样式。
"""
import argparse
import copy
import json
import sys
from pathlib import Path

from docx import Document

sys.stdout.reconfigure(encoding='utf-8')

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
XML_SPACE = '{http://www.w3.org/XML/1998/namespace}space'

# 母版 body 元素索引（换母版时用 spec 的 anchors 覆盖）
DEFAULT_ANCHORS = {
    'title': 0,
    'blank': 1,
    'meta_time': 2,
    'meta_place': 3,
    'meta_host': 4,
    'meta_attend': 5,
    'meta_recorder': 6,
    'h1': 8,
    'num': 9,
    'summary': 13,
    'topic': 14,
    'conclusion': 15,
    'decision_label': 16,
    'decision': 17,
    'h1_action': 34,
    'table': 35,
    'sign': 36,
}

META_LABELS = {
    'time': '会议时间：',
    'place': '会议地点：',
    'host': '主 持 人：',
    'attend': '参会人员：',
    'recorder': '记 录 人：',
}


def set_text(el, texts):
    """按文档顺序写入 w:t；多余的清空，不足时克隆最后一个 run。"""
    texts = list(texts)
    ts = el.findall('.//' + W + 't')
    runs = el.findall(W + 'r') or el.findall('.//' + W + 'r')
    for i, t in enumerate(ts):
        t.text = texts[i] if i < len(texts) else ''
        t.set(XML_SPACE, 'preserve')
    if len(texts) > len(ts) and ts:
        last_run = None
        for r in runs:
            if ts[-1] in list(r.iter(W + 't')):
                last_run = r
        if last_run is None and runs:
            last_run = runs[-1]
        if last_run is not None:
            for extra in texts[len(ts):]:
                nr = copy.deepcopy(last_run)
                for t in nr.iter(W + 't'):
                    t.text = extra
                    t.set(XML_SPACE, 'preserve')
                last_run.addnext(nr)
                last_run = nr


def txt(el):
    return ''.join(t.text or '' for t in el.iter(W + 't'))


def fill_row(tr, values):
    tcs = tr.findall(W + 'tc')
    for i, tc in enumerate(tcs):
        set_text(tc, [values[i] if i < len(values) else ''])


def build(spec, template_path):
    doc = Document(str(template_path))
    body = doc.element.body
    els = list(body.iterchildren())
    anchors = dict(DEFAULT_ANCHORS)
    anchors.update(spec.get('anchors') or {})

    # 先深拷贝所有锚点，再清空 body（保留 sectPr，否则页面设置和落款结构会丢）
    sectPr = body.find(W + 'sectPr')
    pool = {}
    for key, idx in anchors.items():
        pool[key] = copy.deepcopy(els[idx])

    # 只保留 sectPr；切片赋值一次性替换，避免逐个元素移除
    body[:] = [sectPr] if sectPr is not None else []

    def emit(key, texts=None):
        el = copy.deepcopy(pool[key])
        if texts is not None:
            set_text(el, texts)
        if sectPr is not None:
            sectPr.addprevious(el)
        else:
            body.append(el)
        return el

    # 标题
    emit('title', [spec.get('title', '会 议 纪 要')])
    emit('blank')

    # 元信息 5 行
    meta = spec.get('meta') or {}
    for key in ('time', 'place', 'host', 'attend', 'recorder'):
        emit('meta_' + key, [META_LABELS[key], meta.get(key, '')])
    emit('blank')

    # 一、会议目的
    emit('h1', ['一、会议目的'])
    for line in spec.get('purpose') or []:
        emit('num', [line])

    # 二、核心议题、关键结论与决策
    emit('h1', ['二、核心议题、关键结论与决策'])
    if spec.get('summary'):
        emit('summary', [spec['summary']])
    for tp in spec.get('topics') or []:
        emit('topic', [tp['title']])
        emit('conclusion', ['- 关键结论：', tp.get('conclusion', '')])
        emit('decision_label', ['- 决策事项：'])
        emit('decision', [tp.get('decision', '')])

    # 三、行动项
    emit('h1_action', [spec.get('action_title', '三、 行动项 (Action Items)')])
    actions = spec.get('actions') or []
    if actions:
        tbl = copy.deepcopy(pool['table'])
        trs = tbl.findall(W + 'tr')
        header = trs[0]
        row_tpl = trs[1] if len(trs) > 1 else copy.deepcopy(trs[0])
        tbl[:] = [header]
        for a in actions:
            nr = copy.deepcopy(row_tpl)
            fill_row(nr, [a.get('no', ''), a.get('content', ''),
                          a.get('owner', ''), a.get('priority', '')])
            tbl.append(nr)
        if sectPr is not None:
            sectPr.addprevious(tbl)
        else:
            body.append(tbl)

    # 四、补充说明（默认关闭）
    if spec.get('include_supplement') and spec.get('supplement'):
        emit('h1', ['四、 补充说明'])
        emit('summary', [spec['supplement']])

    # 落款
    if spec.get('sign_date'):
        emit('sign', [spec['sign_date']])

    return doc


def main():
    ap = argparse.ArgumentParser(description='按母版生成会议纪要 docx')
    ap.add_argument('spec', help='spec.json 路径')
    args = ap.parse_args()

    spec_path = Path(args.spec).resolve()
    spec = json.loads(spec_path.read_text(encoding='utf-8'))

    tpl = spec.get('template')
    if tpl:
        template_path = Path(tpl)
        if not template_path.is_absolute():
            template_path = (spec_path.parent / template_path).resolve()
    else:
        template_path = Path(__file__).resolve().parent.parent / 'assets' / 'template_standard.docx'
    if not template_path.exists():
        print('母版不存在: %s' % template_path)
        return 2

    out = spec.get('output')
    if not out:
        print('spec 缺少 output')
        return 2
    out_path = Path(out)
    if not out_path.is_absolute():
        out_path = (spec_path.parent / out_path).resolve()
    if out_path.exists() and not spec.get('overwrite'):
        print('目标已存在，拒绝覆盖（需要覆盖请在 spec 里设 overwrite=true）: %s' % out_path)
        return 3
    out_path.parent.mkdir(parents=True, exist_ok=True)

    doc = build(spec, template_path)
    doc.save(str(out_path))

    d = Document(str(out_path))
    print('已生成: %s' % out_path)
    print('顶层元素数: %d' % len(list(d.element.body.iterchildren())))
    print('sections: %d' % len(d.sections))
    print('行动项行数: %d' % len(spec.get('actions') or []))
    return 0


if __name__ == '__main__':
    sys.exit(main())
