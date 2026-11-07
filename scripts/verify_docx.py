# -*- coding: utf-8 -*-
"""会议纪要格式校验：逐项比对规格表，输出 PASS/FAIL 报告。

用法：
    python verify_docx.py <生成的.docx>

退出码：0 全部通过；1 存在 FAIL；2 无法读取。
"""
import sys
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

sys.stdout.reconfigure(encoding='utf-8')

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

EXPECT = {
    'page_w_cm': 21.0,
    'page_h_cm': 29.7,
    'margin_lr_cm': 3.18,
    'margin_tb_cm': 2.54,
    'title_font': '仿宋_GB2312',
    'title_sz': '96',
    'title_color': 'FF0000',
    'body_sz': '28',
    'conclusion_ind_left': '567',
    'num_ind_firstline': '480',
    'table_widths': ['835', '4992', '1332', '1165'],
}


def txt(el):
    return ''.join(t.text or '' for t in el.iter(W + 't'))


def rpr_of_first_run(el):
    r = el.find(W + 'r')
    if r is None:
        r = el.find('.//' + W + 'r')
    if r is None:
        return {}
    rPr = r.find(W + 'rPr')
    if rPr is None:
        return {}
    out = {}
    f = rPr.find(W + 'rFonts')
    if f is not None:
        out['font'] = f.get(W + 'eastAsia') or f.get(W + 'ascii')
    sz = rPr.find(W + 'sz')
    if sz is not None:
        out['sz'] = sz.get(W + 'val')
    c = rPr.find(W + 'color')
    if c is not None:
        out['color'] = c.get(W + 'val')
    out['b'] = rPr.find(W + 'b') is not None
    return out


def ppr_of(el):
    pPr = el.find(W + 'pPr')
    if pPr is None:
        return {}
    out = {}
    jc = pPr.find(W + 'jc')
    if jc is not None:
        out['jc'] = jc.get(W + 'val')
    ind = pPr.find(W + 'ind')
    if ind is not None:
        out['left'] = ind.get(W + 'left')
        out['firstLine'] = ind.get(W + 'firstLine')
    return out


def check(results, name, ok, actual, expect):
    results.append((name, 'PASS' if ok else 'FAIL', str(actual), str(expect)))


def main():
    if len(sys.argv) < 2:
        print('用法: python verify_docx.py <docx>')
        return 2
    p = Path(sys.argv[1])
    if not p.exists():
        print('文件不存在: %s' % p)
        return 2

    doc = Document(str(p))
    body = doc.element.body
    els = [e for e in body.iterchildren() if e.tag != W + 'sectPr']
    res = []

    # 页面
    s = doc.sections[0] if doc.sections else None
    check(res, 'sectPr 存在', body.find(W + 'sectPr') is not None,
          body.find(W + 'sectPr') is not None, True)
    if s:
        check(res, '纸张 A4 宽', abs(s.page_width.cm - EXPECT['page_w_cm']) < 0.2,
              round(s.page_width.cm, 2), EXPECT['page_w_cm'])
        check(res, '纸张 A4 高', abs(s.page_height.cm - EXPECT['page_h_cm']) < 0.2,
              round(s.page_height.cm, 2), EXPECT['page_h_cm'])
        check(res, '左右页边距', abs(s.left_margin.cm - EXPECT['margin_lr_cm']) < 0.05,
              round(s.left_margin.cm, 2), EXPECT['margin_lr_cm'])
        check(res, '上下页边距', abs(s.top_margin.cm - EXPECT['margin_tb_cm']) < 0.05,
              round(s.top_margin.cm, 2), EXPECT['margin_tb_cm'])

    # 标题
    title = els[0] if els else None
    if title is not None:
        r = rpr_of_first_run(title)
        pp = ppr_of(title)
        check(res, '标题文字', txt(title).strip() == '会 议 纪 要', txt(title).strip(), '会 议 纪 要')
        check(res, '标题字体', r.get('font') == EXPECT['title_font'], r.get('font'), EXPECT['title_font'])
        check(res, '标题字号', r.get('sz') == EXPECT['title_sz'], r.get('sz'), EXPECT['title_sz'])
        check(res, '标题红色', r.get('color') == EXPECT['title_color'], r.get('color'), EXPECT['title_color'])
        check(res, '标题加粗', r.get('b') is True, r.get('b'), True)
        check(res, '标题居中', pp.get('jc') == 'center', pp.get('jc'), 'center')

    # 元信息 5 行
    labels = ['会议时间：', '会议地点：', '主 持 人：', '参会人员：', '记 录 人：']
    for i, lab in enumerate(labels, start=2):
        if i < len(els):
            t = txt(els[i])
            check(res, '元信息 %d 标签' % (i - 1), lab.replace(' ', '') in t.replace(' ', ''), t[:20], lab)

    # 正文段落抽样：编号段缩进、关键结论缩进、字号
    num_inds = []
    kj_lefts = []
    body_szs = []
    for idx, el in enumerate(els):
        if el.tag != W + 'p':
            continue
        if idx == 0:  # 标题段不参与正文校验
            continue
        pp = ppr_of(el)
        t = txt(el)
        if t.startswith('- 关键结论：'):
            kj_lefts.append(pp.get('left'))
        if len(t) > 2 and t[0].isdigit() and t[1] in '.、' and pp.get('firstLine'):
            num_inds.append(pp.get('firstLine'))
        for r in el.findall(W + 'r'):
            rPr = r.find(W + 'rPr')
            if rPr is not None:
                sz = rPr.find(W + 'sz')
                if sz is not None:
                    body_szs.append(sz.get(W + 'val'))
    check(res, '编号段首行缩进 480', all(v == EXPECT['num_ind_firstline'] for v in num_inds) and num_inds,
          set(num_inds), EXPECT['num_ind_firstline'])
    check(res, '关键结论左缩进 567', all(v == EXPECT['conclusion_ind_left'] for v in kj_lefts) and kj_lefts,
          set(kj_lefts), EXPECT['conclusion_ind_left'])
    check(res, '正文字号 28', set(body_szs) <= {EXPECT['body_sz']}, sorted(set(body_szs)), EXPECT['body_sz'])

    # 表格
    tbl = None
    for el in els:
        if el.tag == W + 'tbl':
            tbl = el
    if tbl is None:
        check(res, '行动项表格存在', False, 'None', 'tbl')
    else:
        trs = tbl.findall(W + 'tr')
        check(res, '表头四列', len(trs[0].findall(W + 'tc')) == 4, len(trs[0].findall(W + 'tc')), 4)
        widths = []
        for tc in trs[0].findall(W + 'tc'):
            tcPr = tc.find(W + 'tcPr')
            w = tcPr.find(W + 'tcW') if tcPr is not None else None
            widths.append(w.get(W + 'w') if w is not None else '-')
        check(res, '列宽一致', widths == EXPECT['table_widths'], widths, EXPECT['table_widths'])
        check(res, '数据行数 > 0', len(trs) > 1, len(trs) - 1, '>=1')

    # 落款右对齐
    sign = els[-1] if els else None
    if sign is not None:
        check(res, '落款右对齐', ppr_of(sign).get('jc') == 'right', ppr_of(sign).get('jc'), 'right')

    width = max(len(r[0]) for r in res) + 2
    print('%-*s %-4s %-22s %s' % (width, '校验项', '结果', '实际', '期望'))
    print('-' * (width + 60))
    for name, st, actual, expect in res:
        print('%-*s %-4s %-30s %s' % (width, name, st, actual[:30], expect))
    failed = [r for r in res if r[1] == 'FAIL']
    print('\n合计 %d 项，通过 %d，失败 %d' % (len(res), len(res) - len(failed), len(failed)))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
