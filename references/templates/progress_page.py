#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""项目进度页投影脚本（skill 侧母版：references/templates/progress_page.py）

────────────────────────────────────────────────────────────────────────
它是什么
  把项目里的 MD 权威源「投影」进进度页 HTML 的 DATA 区 —— 只改 `stage` 与 `stages` 两块
  字面量与一行 `updated`；**DATA 区之外（渲染代码等）一个字符都不动**。

落点
  skill 侧母版：`references/templates/progress_page.py`
  项目侧副本  ：`engineering/progress_page.py`（立项时由主控复制过去）
  目标页面    ：`docs/项目进度.html`（固定名、不带日期；由 `references/templates/progress.html` 派生）

触发者（五条约束之五）
  **只有主控对话能触发本脚本**（同款约定写进项目 `AGENTS.md` §九）。
  执行方 / 子 Agent 不得自行重跑投影 —— 本页是「投影件」，权威源永远是 MD。

五条约束（口径见 `references/progress-page.md`）
  1. **只读 MD** —— 对 `MEMORY.md` / `ROADMAP.md` 只读，**绝不写回**；
  2. **幂等** —— 同一份输入跑两次，输出逐字节相同；
  3. **默认 dry-run** —— 只打印「将要改哪几处（旧值 → 新值）」，加 `--write` 才落盘；
  4. **解析失败报错退出**（非零退出码），**绝不产出半成品页面**；
  5. **只有主控能触发**（见上）。

幂等与 `updated` 的关系（重要，别改回去）
  `DATA.updated` 是「页面数据截止时间」。
  **只有投影内容（stage / stages）真的变了，才把 updated 刷成当前时间**；
  若投影内容与页面一致 ⇒ **整页一个字节都不动**（dry-run 打印「无改动」，`--write` 也不落盘）。
  这样「同输入跑两次逐字节相同」是稳定成立的，而不是靠「两次恰好跑在同一分钟」。

权威源链（N1）
  · 阶段路线（stages）：优先 `ROADMAP.md` §二「阶段表」；**没有 ROADMAP.md 时**读
    `MEMORY.md` §2 的「阶段路线（起点，可增删改名）：A → B → C；当前：X」那一行。
    判定「哪条是路线行」＝**含「阶段路线」且带「当前：」标记**（只认前者会把普通进展
    条目里提到「阶段路线」的句子也当成路线行）。
    ROADMAP.md 存在但 §二 缺失/为空 ⇒ **报错退出**（不静默回退 MEMORY —— 那正是
    「看着跑通了、其实读的是旧权威源」的坑）。
  · 当前状态（stage）：`name` ＝ 当前节点名（ROADMAP 路径带 `阶段 N · ` 前缀，与模板
    占位符 `{{阶段名，如：阶段 1 · 准备}}` 同形）；`line` ＝ `ROADMAP.md` §三
    「当前唯一卡点」正文，没有（或为空）时退回 `MEMORY.md` §2 最新一条。
    取来的文字一律去 Markdown 强调标记（`**` / 反引号 / 行首 `- `）、**剥掉行首日期前缀**
    （`<20261018>：` / `2026-10-18：` 这一类 —— 页面另有一个独立的「数据截止」字段，
    行首再带一遍日期是噪音），并压成一行。

阶段状态映射
  · MEMORY 路径：路线里「当前」之前的节点 → `done`；「当前」→ `doing`；其余 → `todo`。
    找不到「当前：」标记 ⇒ 报错退出。
  · ROADMAP 路径：§二 状态列符号表 —— `✅`/`✔`/`☑` → `done`；`🔄`/`🚧` → `doing`；
    其余（`⬜`／空／其它）→ `todo`。
    `doing` 超过一个 ⇒ 报错退出；**全表没有 doing ⇒ 放行**（按收尾处理：`stage.name`
    取最后一个 `done` 节点），并在输出里明确打印这一句。
  · 两条路径都保证：`done` 必须在前、`doing` 至多一个。（ROADMAP 路径若表里
    「done 之后还有未完成节点」，只提示、不改表 —— 页面按表原样投影。）

用法
  python progress_page.py <项目根目录>                    # dry-run：只打印将改哪几处
  python progress_page.py <项目根目录> --write            # 落盘
  python progress_page.py <项目根目录> --page <页面路径>   # 显式指定页面
  python progress_page.py --help

  页面默认取 `<根>/docs/` 下唯一一个 `项目进度*.html`；0 个或 ≥2 个 ⇒ 报错，要求显式 `--page`。

  **页面模板保持干净、不加任何标记**（`references/templates/progress.html`：没有锚点注释），
  所以定位全靠结构，**不解析 HTML 里的 JS**：
    ① 找唯一的 `var DATA = {` … 其后第一个顶格 `};` —— **只在这个区间内做替换**；
    ② 区间内匹配 `  stage: {` … `  },` 与 `  stages: [` … `  ],`（带行首缩进与 `: {` / `: [`
       形态限定 —— 这样渲染代码里的 `DATA.stage` / `DATA.stages` 不会被误伤），整块换掉；
    ③ `updated:` 用单行正则（同样只在这个区间内）。
  匹配不到或匹配到多处 ⇒ 报错退出（**不猜、不兜底插入**）。改完还做一次自检：
  渲染代码里 `DATA.stage` / `DATA.stages` 的引用数必须一处未变，不过就不写盘。

退出码
  0 成功；1 投影失败（源缺 / 解析失败 / DATA 区或 stage、stages 结构认不出 / 读写失败）；2 命令行用法错误。
"""

import argparse
import datetime
import glob
import os
import re
import sys

# ── 常量（口径集中在这里，改口径只改这几行）────────────────────────────────
PAGE_GLOB = '项目进度*.html'
ROUTE_KEY = '阶段路线'
CURRENT_RE = re.compile(r'当前\s*[：:]')
DONE_SYMBOLS = ('✅', '✔', '☑')
DOING_SYMBOLS = ('🔄', '🚧')
STATE_ORDER = ('done', 'doing', 'todo')
EMPTY_WHEN = '—'

H2_RE = re.compile(r'^##(?!#)\s*(?P<title>.*?)\s*$', re.MULTILINE)
LIST_ITEM_RE = re.compile(r'^\s*[-*+]\s+')
LEAD_DATE_RE = re.compile(r'^<?\d{4}[-/.]?\d{2}[-/.]?\d{2}>?[ \t]*[：:]?[ \t]*')
MD_LINK_RE = re.compile(r'\[([^\]]*)\]\([^)]*\)')
TABLE_SEP_RE = re.compile(r':?-{2,}:?')
LEAD_NUM_RE = re.compile(r'^(\d+)\s*[.、,，)）]?\s*(.+)$')


# ── 基础设施 ───────────────────────────────────────────────────────────────
def _reconfigure_std_streams():
    """Windows 控制台默认编码可能装不下 emoji → 统一成 UTF-8（不崩、不乱码）。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass


def die(msg, code=1):
    """报错退出。绝不继续往下走 —— 也就不会产出半成品页面。"""
    print('错误：' + str(msg), file=sys.stderr)
    raise SystemExit(code)


def read_text(path, encoding='utf-8'):
    """按原样读文本：newline='' ⇒ 不翻译换行，写回时能保持逐字节一致。"""
    with open(path, 'r', encoding=encoding, newline='') as fh:
        return fh.read()


def write_text_atomic(path, text):
    """原子落盘：先写同目录临时文件再替换 —— 中途失败也不会留下半成品页面。"""
    tmp = path + '.tmp-progress'
    try:
        with open(tmp, 'w', encoding='utf-8', newline='') as fh:
            fh.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        raise


def one_line(text, limit=160):
    flat = ' '.join(str(text).split())
    return flat if len(flat) <= limit else flat[:limit] + '…'


def plain(text):
    """压成一行纯文本：去链接语法 / 强调标记 / 反引号，折叠空白。"""
    if text is None:
        return ''
    out = MD_LINK_RE.sub(r'\1', str(text))
    out = out.replace('**', '').replace('__', '').replace('`', '')
    out = out.replace('<br>', ' ')
    return re.sub(r'\s+', ' ', out).strip()


def strip_leading_date(text):
    """剥掉行首日期前缀（如 `<20261018>：` / `2026-10-18：` / `<20261018>`）。

    页面另有一个独立的「数据截止」字段，行首再带一遍日期是噪音。
    若剥完会变空（整行就只有个日期），则原样返回 —— 宁可留着，也不产出空现状。
    """
    stripped = LEAD_DATE_RE.sub('', str(text), count=1).strip()
    return stripped or str(text).strip()


def js_str(text):
    """生成单引号 JS 字符串字面量（转义反斜杠、单引号、控制字符）。"""
    out = str(text).replace('\\', '\\\\').replace("'", "\\'")
    out = out.replace('\r', ' ').replace('\n', ' ')
    out = out.replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    return "'" + out + "'"


# ── MD 解析 ───────────────────────────────────────────────────────────────
def split_h2(md_text):
    """按二级标题切段，返回 [(标题, 正文), …]（`###` 不算）。"""
    marks = list(H2_RE.finditer(md_text))
    out = []
    for i, mark in enumerate(marks):
        start = mark.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(md_text)
        out.append((mark.group('title').strip(), md_text[start:end]))
    return out


def find_section(md_text, key, where):
    """找唯一的二级标题；0 个返回 None（由调用方决定是否算错），多个直接报错。"""
    hits = [sec for sec in split_h2(md_text) if key in sec[0]]
    if len(hits) > 1:
        die('%s 里有 %d 个含「%s」的二级标题（应恰好 1 个）' % (where, len(hits), key))
    return hits[0] if hits else None


def section_list_items(body):
    """取一节的顶格列表条目（跳过引用行、表格行与缩进说明行）。"""
    items = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('>') or stripped.startswith('|'):
            continue
        if LIST_ITEM_RE.match(line):
            items.append(stripped)
    return items


def drop_list_marker(text):
    return LIST_ITEM_RE.sub('', str(text).strip()).strip()


def drop_date_prefix(text):
    return re.sub(r'^<?\d{8}>?\s*[：:]\s*', '', str(text).strip()).strip()


def first_text_block(body):
    """取一节里第一段正文（跳过表格 / 引用 / 小标题）；没有则退回第一个列表条目。"""
    buf = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            if buf:
                break
            continue
        if stripped.startswith(('|', '>', '#')) or LIST_ITEM_RE.match(line):
            if buf:
                break
            continue
        buf.append(stripped)
    if buf:
        return plain(' '.join(buf))
    for line in body.splitlines():
        if LIST_ITEM_RE.match(line):
            return plain(drop_list_marker(line))
    return ''


def parse_md_table(body):
    """解析一节里的第一张 MD 表（跳表头与分隔行）。"""
    raw = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith('|'):
            raw.append([cell.strip() for cell in stripped.strip('|').split('|')])
    rows, seen_sep = [], False
    for cells in raw:
        if cells and all(TABLE_SEP_RE.fullmatch(cell) for cell in cells if cell != ''):
            seen_sep = True
            continue
        if not seen_sep:
            continue          # 分隔行之前的都算表头
        rows.append(cells)
    if not rows and len(raw) > 1:
        rows = raw[1:]        # 没有分隔行时，把第一行当表头
    return rows


# ── 权威源：MEMORY 路径 ───────────────────────────────────────────────────
def route_payload(item):
    """从「阶段路线…」那条里取出正文（去掉列表符、日期前缀与「阶段路线…：」）。"""
    text = drop_date_prefix(drop_list_marker(item))
    mark = re.search(r'阶段路线[^：:]*[：:]', text)
    return text[mark.end():].strip() if mark else text


def is_route_line(item):
    """判定一条列表条目是不是「阶段路线」行。

    只用「含『阶段路线』」不够 —— 普通进展条目完全可能写到「阶段路线权威转交
    ROADMAP §二」这类句子，会被误判成第二条路线行（自测夹具就撞过）。
    真正的路线行必然带「当前：」标记，所以两个条件一起用。
    """
    return ROUTE_KEY in item and bool(CURRENT_RE.search(item))


def parse_route(item):
    """解析路线行 → (节点列表, 当前节点名)。任何解析不出都报错退出。"""
    text = drop_date_prefix(drop_list_marker(item))
    mark = re.search(r'阶段路线[^：:]*[：:]', text)
    if not mark:
        die('MEMORY.md §2 的「阶段路线」行里找不到「阶段路线…：」与节点清单')
    segment = re.split(r'[；;。]', text[mark.end():], maxsplit=1)[0]
    nodes = [plain(part) for part in re.split(r'→|->', segment)]
    nodes = [node for node in nodes if node]
    if not nodes:
        die('MEMORY.md §2 的「阶段路线」行里没解析出任何节点（节点之间用 → 分隔）')

    hits = CURRENT_RE.findall(text)
    if not hits:
        die('MEMORY.md §2 的「阶段路线」行里找不到「当前：」标记 —— 权威源不完整，不猜')
    if len(hits) > 1:
        die('MEMORY.md §2 的「阶段路线」行里有 %d 个「当前：」标记（应恰好 1 个）' % len(hits))
    tail = CURRENT_RE.split(text, maxsplit=1)[1]
    current = plain(re.split(r'[；;。，,*]', tail, maxsplit=1)[0])
    if not current:
        die('MEMORY.md §2 的「阶段路线」行里「当前：」后面是空的')
    if nodes.count(current) > 1:
        die('阶段路线里「%s」出现多次（%s）—— 无法确定当前节点' % (current, ' → '.join(nodes)))
    if current not in nodes:
        die('「当前：%s」不在阶段路线里（路线：%s）' % (current, ' → '.join(nodes)))
    return nodes, current


def memory_status_from_items(items):
    """§2 最新一条 → 现状一句话（跳过路线行本身）。"""
    for item in items:
        if not is_route_line(item):
            return plain(drop_list_marker(item))
    return plain(route_payload(items[0])) if items else ''


def stages_from_memory(items):
    route_items = [item for item in items if is_route_line(item)]
    if not route_items:
        die('MEMORY.md §2 里找不到「阶段路线（起点，可增删改名）：…；当前：X」那一行 —— '
            '它是 ROADMAP.md 建立前的阶段路线权威源（且必须带「当前：」标记），不猜、不兜底')
    if len(route_items) > 1:
        die('MEMORY.md §2 里有 %d 条「阶段路线」行（应恰好 1 条）' % len(route_items))
    nodes, current = parse_route(route_items[0])
    index = nodes.index(current)
    stages = []
    for i, name in enumerate(nodes):
        state = 'done' if i < index else ('doing' if i == index else 'todo')
        stages.append({'n': '阶段 %d' % i, 'name': name, 'state': state,
                       'when': EMPTY_WHEN, 'desc': ''})
    return stages, stages[index]


# ── 权威源：ROADMAP 路径 ──────────────────────────────────────────────────
def map_state_symbol(cell):
    text = str(cell)
    for symbol in DONE_SYMBOLS:
        if symbol in text:
            return 'done'
    for symbol in DOING_SYMBOLS:
        if symbol in text:
            return 'doing'
    return 'todo'


def stages_from_roadmap(md_text, notes):
    section = find_section(md_text, '阶段表', 'ROADMAP.md')
    if section is None:
        die('ROADMAP.md 存在，但找不到含「阶段表」的二级标题（§二）—— 不静默回退 MEMORY，'
            '请先补 ROADMAP §二 阶段表')
    rows = parse_md_table(section[1])
    if not rows:
        die('ROADMAP.md §二 阶段表里没有解析到任何数据行（回退 MEMORY 会更糟，故直接报错）')

    stages = []
    for i, cells in enumerate(rows, 1):
        name_cell = plain(cells[0]) if cells else ''
        state_cell = cells[1] if len(cells) > 1 else ''
        desc_cell = plain(cells[2]) if len(cells) > 2 else ''
        if not name_cell:
            die('ROADMAP.md §二 阶段表第 %d 行的「阶段」列是空的' % i)
        match = LEAD_NUM_RE.match(name_cell)
        if match:
            number, name = match.group(1), match.group(2).strip()
        else:
            number, name = str(i), name_cell
        stages.append({'n': '阶段 ' + number, 'name': name,
                       'state': map_state_symbol(state_cell),
                       'when': EMPTY_WHEN, 'desc': desc_cell})

    doings = [i for i, stage in enumerate(stages) if stage['state'] == 'doing']
    if len(doings) > 1:
        die('ROADMAP.md §二 里有 %d 个 doing（%s）—— 只允许一个'
            % (len(doings), '、'.join(stages[i]['name'] for i in doings)))
    if doings:
        current = stages[doings[0]]
    else:
        notes.append('全表无 doing，按收尾处理：stage.name 取最后一个 done 节点')
        dones = [i for i, stage in enumerate(stages) if stage['state'] == 'done']
        if not dones:
            die('ROADMAP.md §二 阶段表全是「未开始」，无法确定当前阶段 —— '
                '请先把当前那一段标成 🔄/🚧；或先删掉 ROADMAP.md，让权威源退回 MEMORY.md §2')
        current = stages[dones[-1]]

    seen_pending = False
    for stage in stages:
        if stage['state'] != 'done':
            seen_pending = True
        elif seen_pending:
            notes.append('注意：阶段表里 done 之后还有未完成节点（「done 在前」被打破）'
                         '—— 页面按表原样投影，不改表')
            break
    return stages, current


# ── 组装投影内容 ──────────────────────────────────────────────────────────
def load_sources(root):
    """只读 MD，产出投影内容。这里绝不写任何文件。"""
    memory_path = os.path.join(root, 'MEMORY.md')
    roadmap_path = os.path.join(root, 'ROADMAP.md')
    memory_text = read_text(memory_path, 'utf-8-sig') if os.path.isfile(memory_path) else None
    roadmap_text = read_text(roadmap_path, 'utf-8-sig') if os.path.isfile(roadmap_path) else None
    notes = []

    if roadmap_text is not None:
        stages, current = stages_from_roadmap(roadmap_text, notes)
        authority = 'ROADMAP.md §二（阶段表）'
        stage_name = '%s · %s' % (current['n'], current['name'])
        line = ''
        section = find_section(roadmap_text, '卡点', 'ROADMAP.md')
        if section is not None:
            line = first_text_block(section[1])
        if not line:
            line = memory_status_from_items_soft(memory_text)
            if line:
                notes.append('ROADMAP.md §三 没有正文 ⇒ stage.line 退回 MEMORY.md §2 最新一条')
            authority += '；§三 无正文'
        else:
            authority += ' ＋ §三（当前唯一卡点）'
    else:
        if memory_text is None:
            die('找不到 %s —— 没有 MEMORY.md 就没有阶段路线权威源' % memory_path)
        section = find_section(memory_text, '当前状态', 'MEMORY.md')
        if section is None:
            die('MEMORY.md 里找不到含「当前状态」的二级标题（§2）')
        items = section_list_items(section[1])
        if not items:
            die('MEMORY.md §2 里没有任何列表条目 —— 阶段路线行与最新一条都在这一节')
        stages, current = stages_from_memory(items)
        authority = 'MEMORY.md §2（阶段路线行）'
        stage_name = current['name']
        line = memory_status_from_items(items)
        if line:
            authority += ' ＋ §2 最新一条'

    stage_line = strip_leading_date(line)
    if not stage_name and not stage_line:
        die('既没有当前阶段名、也没有现状一句话 —— 无法投影状态区')
    return {'authority': authority, 'stage_name': stage_name, 'stage_line': stage_line,
            'stages': stages, 'notes': notes}


def memory_status_from_items_soft(memory_text):
    """宽松版：MEMORY 缺失/结构不全时返回 ''，不报错（ROADMAP 路径下它只是后退来源）。"""
    if not memory_text:
        return ''
    section = find_section(memory_text, '当前状态', 'MEMORY.md')
    if section is None:
        return ''
    items = section_list_items(section[1])
    return memory_status_from_items(items) if items else ''


def counts_text(stages):
    counts = {state: 0 for state in STATE_ORDER}
    for stage in stages:
        counts[stage['state']] = counts.get(stage['state'], 0) + 1
    return '%d 段（done %d / doing %d / todo %d）' % (
        len(stages), counts['done'], counts['doing'], counts['todo'])


def build_stage_body(src, indent, newline):
    """生成 `stage: { … },` 整块（**不含行尾换行** —— 原换行留在页面里不动）。"""
    lines = [
        indent + 'stage: {',
        indent + '  name: %s,' % js_str(src['stage_name']),
        indent + '  line: %s' % js_str(src['stage_line']),
        indent + '},',
    ]
    return newline.join(lines)


def build_stages_body(src, indent, newline):
    """生成 `stages: [ … ],` 整块（**不含行尾换行**）。"""
    lines = [indent + 'stages: [']
    for stage in src['stages']:
        lines.append(indent + '  {n:%s, name:%s, state:%s, when:%s, desc:%s},' % (
            js_str(stage['n']), js_str(stage['name']), js_str(stage['state']),
            js_str(stage['when']), js_str(stage['desc'])))
    lines.append(indent + '],')
    return newline.join(lines)


# ── 页面：定位 DATA 区 → 区内的 stage / stages 两块 → updated 行 ────────────
# 页面模板保持干净、不加任何标记（没有锚点注释），所以定位全靠结构：
#   ① 先在页面里找唯一的 `var DATA = {` … 其后第一个顶格 `};` —— **只在这个区间内动**；
#   ② 区间内匹配 `  stage: {` … `  },` 与 `  stages: [` … `  ],`（带行首缩进与 `: {` / `: [`
#      形态限定 —— 这样渲染代码里的 `DATA.stage` / `DATA.stages` 不会被误伤）；
#   ③ 匹配不到 / 匹配到多处 ⇒ 报错退出，**绝不猜、绝不兜底插入**。
DATA_HEAD = 'var DATA = {'
DATA_TAIL_RE = re.compile(r'(?m)^\};')
STAGE_BLOCK_RE = re.compile(
    r'(?ms)^(?P<indent>[ \t]*)stage[ \t]*:[ \t]*\{(?P<body>.*?)^(?P=indent)\},[ \t]*(?=\r?\n|\Z)')
STAGES_BLOCK_RE = re.compile(
    r'(?ms)^(?P<indent>[ \t]*)stages[ \t]*:[ \t]*\[(?P<body>.*?)^(?P=indent)\],[ \t]*(?=\r?\n|\Z)')
UPDATED_RE = re.compile(r"(?m)^(?P<pre>[ \t]*updated[ \t]*:[ \t]*')(?P<val>[^'\r\n]*)'")


def locate_data_region(text):
    """定位 DATA 区，返回花括号内部的 [start, end) 偏移。"""
    heads = list(re.finditer(re.escape(DATA_HEAD), text))
    if not heads:
        die('页面里找不到 `%s` —— 这不是本脚本认识的进度页；不猜、不兜底插入' % DATA_HEAD)
    if len(heads) > 1:
        die('页面里 `%s` 出现 %d 次（应恰好 1 次）—— 不猜，请人工确认' % (DATA_HEAD, len(heads)))
    start = heads[0].end()
    tail = DATA_TAIL_RE.search(text, start)
    if tail is None:
        die('页面里 `%s` 之后找不到顶格收尾的 `};` —— 结构不认识，不猜、不兜底插入' % DATA_HEAD)
    return start, tail.start()


def region_newline(region):
    """DATA 区的换行风格（必须统一，否则拒绝动手）。"""
    crlf = region.count('\r\n')
    lf = region.count('\n') - crlf
    if crlf and lf:
        die('DATA 区里混用了 CRLF 与 LF 两种换行（%d / %d）—— 请先统一，再跑投影' % (crlf, lf))
    return '\r\n' if crlf else '\n'


def find_block(region, pattern, label):
    """区间内定位唯一的一块；0 处或多处都报错退出。"""
    matches = list(pattern.finditer(region))
    if not matches:
        die('页面 DATA 区里找不到 `%s:` 那一块（要求形如 `%s: { … },` 或 `%s: [ … ],`，'
            '且起行带缩进）—— 不猜、不兜底插入' % (label, label, label))
    if len(matches) > 1:
        die('页面 DATA 区里 `%s:` 匹配到 %d 处（应恰好 1 处）—— 不猜，请人工确认'
            % (label, len(matches)))
    return matches[0]


def find_updated(region):
    """区间内定位唯一的 `updated: '…'` 行。"""
    matches = list(UPDATED_RE.finditer(region))
    if not matches:
        die('页面 DATA 区里找不到 `updated: \'…\'` 那一行 —— 不猜、不兜底插入')
    if len(matches) > 1:
        die('页面 DATA 区里 `updated:` 行出现 %d 次（应恰好 1 次）' % len(matches))
    match = matches[0]
    return {'match': match, 'value': match.group('val')}


def count_refs(text, token):
    """数渲染代码里的 `DATA.stage` / `DATA.stages` 引用（用来证明没被误伤）。"""
    return len(re.findall(re.escape(token) + r'\b', text))


# ── 命令行 ────────────────────────────────────────────────────────────────
def resolve_page(root, page_arg):
    if page_arg:
        path = page_arg if os.path.isabs(page_arg) else os.path.join(root, page_arg)
        if not os.path.isfile(path):
            die('指定的页面不存在：%s' % path)
        return os.path.abspath(path)
    candidates = sorted(glob.glob(os.path.join(root, 'docs', PAGE_GLOB)))
    if not candidates:
        die('在 %s 下找不到 `%s` —— 用 --page 显式指定'
            % (os.path.join(root, 'docs'), PAGE_GLOB))
    if len(candidates) > 1:
        die('找到 %d 个候选页面，请用 --page 显式指定：\n  %s'
            % (len(candidates), '\n  '.join(candidates)))
    return os.path.abspath(candidates[0])


# ── 收尾体检（--check）：把「任务链 / 提示词 / updated」三条文字规则变成可执行 ──
# 只读页面，不写盘。退出码 0 ＝ 通过；3 ＝ 有未通过项。
CHECK_EMPTY_HINT = ('任务链、待拍板、提示词全为空 —— 若不是本轮已收口，请补 next ／ prompts；'
                    '若确已收口，在 next 里写 idle: true')

STATE_BAD = ('已完成', '已定', '已移出')


def _block(region, key):
    """取 key 对应数组的内容：按引号与括号扫描，字符串里的 `]` 不截断。"""
    m = re.search(r'(?m)^[ \t]*' + key + r'[ \t]*:[ \t]*\[', region)
    if not m:
        return None
    start = m.end() - 1
    depth = 0
    quote = None
    j = start
    while j < len(region):
        ch = region[j]
        if quote:
            if ch == '\\':
                j += 2
                continue
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                return region[start + 1:j]
        j += 1
    return None


def run_check(region):
    problems = []
    ready = _block(region, 'ready')
    decide = _block(region, 'decide')
    current = _block(region, 'current')
    used = _block(region, 'used')
    queue = _block(region, 'queue')
    if ready is None or decide is None or current is None:
        return ['DATA 区缺 next.ready ／ next.decide ／ prompts.current 之一 —— 结构不认识，不猜']

    for st in re.findall(r"state\s*:\s*'([^']*)'", ready):
        if st in STATE_BAD:
            problems.append('任务链里挂着「%s」项 —— 做完的应移入 timeline ／ next.decided' % st)

    names_cur = set(re.findall(r"name\s*:\s*'([^']*)'", current))
    names_used = set(re.findall(r"name\s*:\s*'([^']*)'", used or ''))
    dup = names_cur & names_used
    if dup:
        problems.append('提示词在 current 与 used 重复：%s —— 已派发的应立即移出 current' % '、'.join(sorted(dup)))

    if (not ready.strip() and not decide.strip() and not current.strip()
            and not (queue or '').strip()
            and not re.search(r'(?m)^[ \t]*idle[ \t]*:[ \t]*true\b', region)):
        problems.append(CHECK_EMPTY_HINT)

    up = UPDATED_RE.search(region)
    if not up:
        problems.append('DATA 区找不到 updated')
    elif not re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$', up.group('val')):
        problems.append('updated 格式应为 YYYY-MM-DD HH:MM（当前 %r）' % up.group('val'))

    if '{{' in region:
        problems.append('DATA 区仍有 {{…}} 占位符未替换 —— 交付的必须是填好的成品页')

    return problems


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog='progress_page.py',
        description='项目进度页投影脚本：把 MEMORY.md / ROADMAP.md 投影进进度页 DATA 区（默认 dry-run）。',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=('示例\n'
                '  python progress_page.py .                 # dry-run：只打印将改哪几处\n'
                '  python progress_page.py . --write         # 落盘\n'
                '  python progress_page.py . --page docs/项目进度.html\n'
                '  python progress_page.py . --check        # 收尾体检（只读）\n'
                '\n'
                '投影范围（v1 只做这三项，其余区块一律不动）\n'
                '  stage 区  ← 当前阶段名 ＋ 现状一句话\n'
                '  stages 区 ← ROADMAP.md §二 阶段表；没有 ROADMAP 时读 MEMORY.md §2 的路线行\n'
                '  updated   ← 运行时时间戳（**仅当投影内容真的变了**才刷新）\n'
                '\n'
                '定位方式（模板不加任何标记，故不依赖标记、只按结构定位）\n'
                '  只在 `var DATA = {` … 顶格 `};` 区间内改；区内 `stage:` / `stages:` 各须恰好 1 处\n'
                '\n'
                '退出码：0 成功；1 投影失败；2 命令行用法错误；3 体检未通过\n'
                '约束：只读 MD、幂等、默认 dry-run、失败不产半成品、只有主控能触发。'))
    parser.add_argument('root', help='项目根目录（含 MEMORY.md / docs/ 的那一层）')
    parser.add_argument('--write', action='store_true',
                        help='真正落盘（默认只 dry-run 打印，不写盘）')
    parser.add_argument('--page', metavar='路径',
                        help='显式指定页面；默认取 <根>/docs/ 下唯一一个 `项目进度*.html`')
    parser.add_argument('--check', action='store_true',
                        help='只做收尾体检（任务链／提示词／updated），不投影、不写盘')
    return parser.parse_args(argv)


def main(argv=None):
    _reconfigure_std_streams()
    args = parse_args(argv)
    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        die('项目根目录不存在或不是目录：%s' % root)

    page_path = resolve_page(root, args.page)
    try:
        page_text = read_text(page_path)
    except OSError as exc:
        die('读不到页面 %s（%s）' % (page_path, exc))

    # ① 只认 DATA 区：区间之外（渲染代码）一个字符都不碰
    data_start, data_end = locate_data_region(page_text)
    region = page_text[data_start:data_end]
    newline = region_newline(region)

    if args.check:
        problems = run_check(region)
        if problems:
            print('✗ 进度页体检未通过（%d 条）：' % len(problems))
            for item in problems:
                print('  - ' + item)
            return 3
        print('✓ 进度页体检通过：无已完成残留、无重复提示词、updated 格式正确')
        return 0

    src = load_sources(root)                                  # 只读 MD（--check 不需要）

    # ② 区间内定位两块（各必须恰好 1 处）
    stage_match = find_block(region, STAGE_BLOCK_RE, 'stage')
    stages_match = find_block(region, STAGES_BLOCK_RE, 'stages')
    old_stage_body = stage_match.group(0)
    old_stages_body = stages_match.group(0)

    new_stage_body = build_stage_body(src, stage_match.group('indent'), newline)
    new_stages_body = build_stages_body(src, stages_match.group('indent'), newline)

    # ③ 整块替换（先 stage 再 stages；每次都在更新后的文本里重新定位）
    new_region = region[:stage_match.start()] + new_stage_body + region[stage_match.end():]
    stages_match = find_block(new_region, STAGES_BLOCK_RE, 'stages')
    new_region = new_region[:stages_match.start()] + new_stages_body + new_region[stages_match.end():]

    stage_changed = old_stage_body != new_stage_body
    stages_changed = old_stages_body != new_stages_body
    content_changed = stage_changed or stages_changed

    updated = find_updated(new_region)
    old_updated = updated['value']
    new_updated = old_updated
    if content_changed:
        new_updated = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        match = updated['match']
        new_region = (new_region[:match.start('val')] + new_updated
                      + new_region[match.end('val'):])

    text = page_text[:data_start] + new_region + page_text[data_end:]

    # ④ 自检：渲染代码里对 DATA.stage / DATA.stages 的引用一处都不许变（误伤即放弃）
    for token in ('DATA.stage', 'DATA.stages'):
        before, after = count_refs(page_text, token), count_refs(text, token)
        if before != after:
            die('自检失败：渲染代码里的 `%s` 引用数被改动（%d → %d）—— 已放弃，页面未动'
                % (token, before, after))

    changes = []
    if stage_changed:
        changes.append(('①', 'stage 区 ', one_line(old_stage_body), one_line(new_stage_body)))
    if stages_changed:
        changes.append(('②', 'stages 区', body_counts_text(old_stages_body)
                        or one_line(old_stages_body), counts_text(src['stages'])))
    if content_changed and new_updated != old_updated:
        changes.append(('③', 'updated  ', "'%s'" % old_updated, "'%s'" % new_updated))

    # ── 报告 ──
    print('页面    ：%s' % page_path)
    print('权威源  ：%s' % src['authority'])
    print('当前阶段：%s' % (src['stage_name'] or '（空）'))
    print('阶段路线：%s' % counts_text(src['stages']))
    for note in src['notes']:
        print('提示    ：%s' % note)

    if not changes:
        print('将改 0 处：投影内容与页面一致（幂等，页面一个字节都不动）')
        if args.write:
            print('未写盘：没有需要改的地方。')
        else:
            print('[dry-run] 未写盘；加 --write 才落盘。')
        return 0

    print('将改 %d 处：' % len(changes))
    for number, label, before, after in changes:
        print('  %s %s：旧 %s' % (number, label, before))
        print('       %s  新 %s' % (' ' * len(label), after))

    if not args.write:
        print('[dry-run] 未写盘；加 --write 才落盘。')
        return 0

    try:
        write_text_atomic(page_path, text)
    except OSError as exc:
        die('写盘失败：%s（%s）—— 页面保持原样（不留半成品）' % (page_path, exc))
    print('已写盘：%s（%d 处改动）' % (page_path, len(changes)))
    return 0


def body_counts_text(body):
    """从页面旧文本里数 done/doing/todo（仅用于 dry-run 摘要；数不出返回 ''）。"""
    values = re.findall(r"state\s*:\s*'([A-Za-z]+)'", body)
    if not values:
        return ''
    counts = {state: 0 for state in STATE_ORDER}
    for value in values:
        if value in counts:
            counts[value] += 1
    return '%d 段（done %d / doing %d / todo %d）' % (
        len(values), counts['done'], counts['doing'], counts['todo'])


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print('已中断（未写盘）。', file=sys.stderr)
        raise SystemExit(130)
