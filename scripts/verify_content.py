# -*- coding: utf-8 -*-
"""会议纪要内容闸：校验 spec.json 的可读性与三类高风险断言。

与 verify_docx.py 的分工：
    verify_docx.py  = 格式闸（排版像不像正式文件）
    verify_content.py = 内容闸（说得对不对、读不读得下去）

用法：
    python verify_content.py <spec.json>

判定分两级：
    FAIL 确定性可自动判定的问题（分句超限、字数超限、结构缺失、优先级非法）
    WARN 需回原文人工核对的高风险断言（数量词 / 绝对化表述 / 方案关系），只提醒不阻断

退出码：0 无 FAIL；1 存在 FAIL；2 无法读取。
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

# ---- 阈值（与 references/writing-guide.md 保持一致）----
MAX_CLAUSES = 4          # 关键结论分句上限
MAX_CHARS = 150          # 关键结论总字数上限（汉字 + 字母数字，不含标点空白）
VALID_PRIORITY = {'高', '较高', '中'}
META_KEYS = ('time', 'place', 'host', 'attend', 'recorder')

# ---- 三类高风险断言的特征词 ----
# 命中不代表错，只代表"必须回原文核对"——摘要常在这些地方失真
RE_QUANTITY = re.compile(
    r'(?:\d+|[一二两三四五六七八九十]+)\s*(?:次|处|轮|批|层|项|条|版|稿)'
    r'|全部|均|每一?个|所有'
)
RE_ABSOLUTE = re.compile(
    r'不能|无法|不支持|不予|不可|做不了|没法|否决|不可行|不成立|无需|禁止|不具备|不允许'
)
RE_PROGRESSION = re.compile(
    r'否则|如无法|只能|推不动|兜底|不得已|退而|末位|最后只'
)
RE_TIMESTAMP = re.compile(r'\[\d{1,2}:\d{2}(?::\d{2})?\]')

CJK_OR_ALNUM = re.compile(r'[\u4e00-\u9fffA-Za-z0-9]')


def count_chars(text):
    """汉字 + 字母数字，不含标点与空白。"""
    return len(CJK_OR_ALNUM.findall(text))


def count_clauses(text):
    """按分号与句号切分句，去掉空段。"""
    parts = [p.strip() for p in re.split(r'[；;。]', text)]
    return len([p for p in parts if p])


def add(res, name, status, actual, expect, detail=''):
    """status 接受 True/False 或 'PASS'/'FAIL'/'WARN'，统一归一化。"""
    if isinstance(status, bool):
        status = 'PASS' if status else 'FAIL'
    res.append((name, status, str(actual), str(expect), detail))


def check_spec(spec):
    res = []

    # ---- 结构完整性（硬闸）----
    topics = spec.get('topics') or []
    actions = spec.get('actions') or []
    purpose = spec.get('purpose') or []
    meta = spec.get('meta') or {}

    add(res, '议题数量 3-6', 3 <= len(topics) <= 6, len(topics), '3-6')
    add(res, '会议目的 >=3', len(purpose) >= 3, len(purpose), '>=3')
    add(res, '行动项 >=1', len(actions) >= 1, len(actions), '>=1')
    missing_meta = [k for k in META_KEYS if k not in meta]
    add(res, '元信息五项齐全', not missing_meta,
        '缺: %s' % ','.join(missing_meta) if missing_meta else '5/5', '5/5')

    # ---- 关键结论可读性（硬闸）----
    worst_clauses, worst_chars = 0, 0
    for i, tp in enumerate(topics, 1):
        c = (tp.get('conclusion') or '').strip()
        d = (tp.get('decision') or '').strip()
        if not c:
            add(res, '议题 %d 关键结论非空' % i, 'FAIL', '空', '非空')
            continue
        if not d:
            add(res, '议题 %d 决策事项非空' % i, 'FAIL', '空', '非空')
        n_cl = count_clauses(c)
        n_ch = count_chars(c)
        worst_clauses = max(worst_clauses, n_cl)
        worst_chars = max(worst_chars, n_ch)
        add(res, '议题 %d 结论分句 <=%d' % (i, MAX_CLAUSES), n_cl <= MAX_CLAUSES,
            n_cl, '<=%d' % MAX_CLAUSES, c[:40] + '...')
        add(res, '议题 %d 结论字数 <=%d' % (i, MAX_CHARS), n_ch <= MAX_CHARS,
            n_ch, '<=%d' % MAX_CHARS, c[:40] + '...')
        # 决策事项必须能看出责任人
        if d and '由' not in d:
            add(res, '议题 %d 决策含责任人' % i, 'FAIL', '未见「由」', '含「由 XXX」', d[:40])

    # ---- 行动项（硬闸）----
    for i, a in enumerate(actions, 1):
        owner = (a.get('owner') or '').strip()
        content = (a.get('content') or '').strip()
        prio = (a.get('priority') or '').strip()
        add(res, '行动项 %d 责任人非空' % i, bool(owner), owner or '空', '非空')
        add(res, '行动项 %d 内容非空' % i, bool(content), '有' if content else '空', '非空')
        add(res, '行动项 %d 优先级合法' % i, prio in VALID_PRIORITY, prio or '空',
            '/'.join(sorted(VALID_PRIORITY)))
        if content and not re.search(r'[（(]', content):
            add(res, '行动项 %d 带截止时间' % i, 'WARN', '无括号时间', '（XX日前/尽快/近期优先）')

    # ---- 三类高风险断言（软闸：只提醒，需回原文核对）----
    for i, tp in enumerate(topics, 1):
        blob = ' '.join([tp.get('title') or '', tp.get('conclusion') or '',
                         tp.get('decision') or ''])
        for label, rx in (('数量词', RE_QUANTITY),
                          ('绝对化表述', RE_ABSOLUTE),
                          ('方案关系', RE_PROGRESSION)):
            hits = sorted(set(rx.findall(blob)))
            if hits:
                add(res, '议题 %d %s需回原文核对' % (i, label), 'WARN',
                    '、'.join(hits[:6]), '已 grep 原文计数/查例外')
        if not RE_TIMESTAMP.search(blob):
            add(res, '议题 %d 结论挂时间戳' % i, 'WARN', '未检出 [mm:ss]', '建议每条挂出处')

    # ---- 元信息待确认（软闸）----
    pending = [k for k in META_KEYS if '待确认' in str(meta.get(k, ''))]
    if pending:
        add(res, '元信息待确认项', 'WARN', '、'.join(pending), '需列入待确认清单并注明推定依据')

    return res, worst_clauses, worst_chars


def main():
    if len(sys.argv) < 2:
        print('用法: python verify_content.py <spec.json>')
        return 2
    p = Path(sys.argv[1])
    if not p.exists():
        print('文件不存在: %s' % p)
        return 2
    try:
        spec = json.loads(p.read_text(encoding='utf-8'))
    except Exception as e:
        print('spec.json 解析失败: %s' % e)
        return 2

    res, worst_clauses, worst_chars = check_spec(spec)

    width = max(len(r[0]) for r in res) + 2
    print('%-*s %-5s %-24s %s' % (width, '校验项', '结果', '实际', '期望'))
    print('-' * (width + 66))
    for name, st, actual, expect, detail in res:
        line = '%-*s %-5s %-26s %s' % (width, name, st, actual[:26], expect)
        if st == 'WARN' and detail:
            line += '   <- ' + detail
        print(line)

    fails = [r for r in res if r[1] == 'FAIL']
    warns = [r for r in res if r[1] == 'WARN']
    print('\n合计 %d 项：通过 %d，FAIL %d，WARN %d'
          % (len(res), len(res) - len(fails) - len(warns), len(fails), len(warns)))
    print('最差分句数 %d / 上限 %d；最差字数 %d / 上限 %d'
          % (worst_clauses, MAX_CLAUSES, worst_chars, MAX_CHARS))
    if fails:
        print('\n存在 FAIL：先修 spec.json 再生成 docx。分句或字数超限时，'
              '把超出的层次改为「- 」分条，每条一个事实层次。')
    if warns:
        print('\nWARN 不代表错，代表「必须回原文核对」：')
        print('  · 数量词    → grep 关键词回原文计数（摘要常把 6 处写成三次）')
        print('  · 绝对化    → 检索该发言人是否给过例外/让步（「可以」「但前提」）')
        print('  · 方案关系  → 「A 否则 B」多为递进，不是并列，勿写成两个可选方案')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
