#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""项目骨架自检（可选工具）。由 project-bootstrap 提供。

**什么时候用**：项目按 skill 立完骨架后、或每次较大改动收尾时，想确认"文档没失真"就跑一次。
**怎么用**：把本文件复制到项目的 `engineering/check_project.py`，然后

    python engineering/check_project.py .
    python engineering/check_project.py . --quiet     # 只报失败项

退出码：0 = 全过；1 = 有失败项。

它查七件事 —— 都是"靠人记会漏"的那类：
  1. 五份骨架文档齐不齐
  2. AGENTS.md 顺序表里标 ☑ 的产物，磁盘上是否真的存在（**状态列失真 = 表等于没有**）
  3. 落盘后有没有残留占位符 `<…>`
  4. 根目录有没有住着产物
  5. 骨架层目录名是不是英文小写
  6. Markdown 表格列数一致
  7. MEMORY.md §2 有没有"阶段路线"那一条
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# 立项必建的骨架文档
CORE_DOCS = ["AGENTS.md", "MEMORY.md", "USER.md", "SOUL.md", "PRD.md"]

# 根目录允许出现的文件（骨架文档 ＋ 门面 ＋ 配置）
ROOT_ALLOWED = {
    "AGENTS.md", "MEMORY.md", "USER.md", "SOUL.md", "PRD.md",
    "ROADMAP.md", "ACCEPTANCE.md", "CONTRACT.md", "README.md",
    "LICENSE", ".gitignore", ".gitattributes", "CHANGELOG.md",
}

# 骨架层允许的目录名（英文小写白名单 ＋ 常见扩展）
SKELETON_DIRS = {
    "content", "engineering", "docs", "notes", "assets", "models",
    "dist", "release", "archive", "logs", "templates", "skills", "src", "tests",
}

results: list[tuple[bool, str, str]] = []


def ok(name: str, detail: str = "") -> None:
    results.append((True, name, detail))


def bad(name: str, detail: str) -> None:
    results.append((False, name, detail))


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def check_core_docs(root: Path) -> None:
    missing = [d for d in CORE_DOCS if not (root / d).exists()]
    if missing:
        bad("骨架文档", "缺：" + "、".join(missing))
    else:
        ok("骨架文档", "五份齐")


def check_order_table(root: Path) -> None:
    """顺序表里标 ☑ 的产物，磁盘上必须真的存在。"""
    p = root / "AGENTS.md"
    if not p.exists():
        bad("顺序表", "AGENTS.md 不存在")
        return

    lines = read(p).split("\n")
    start = None
    for i, l in enumerate(lines):
        if "产物长出来的顺序" in l:
            start = i
            break
    if start is None:
        bad("顺序表", "AGENTS.md 里找不到「产物长出来的顺序」")
        return

    rows, started = [], False
    for l in lines[start:]:
        s = l.strip()
        if s.startswith("|"):
            if not started:
                started = True
                continue
            if set(s) <= set("|-: "):
                continue
            rows.append(s)
        elif started:
            break

    if not rows:
        bad("顺序表", "表里没有数据行")
        return

    wrong = []
    for r in rows:
        cells = [c.strip() for c in r.strip("|").split("|")]
        if len(cells) < 4:
            continue
        name, state = cells[0], cells[-1]
        if "☑" not in state:
            continue
        name = name.replace("`", "").strip()
        for token in name.split():
            token = token.strip("`*")
            if not token:
                continue
            if not (root / token).exists():
                wrong.append(f"标 ☑ 但不存在：{token}")

    if wrong:
        bad("顺序表", "；".join(wrong[:6]))
    else:
        ok("顺序表", f"{len(rows)} 行，☑ 的都在")


def check_placeholders(root: Path) -> None:
    """落盘后不应残留 <…> 占位符（图片 / HTML 标签不算）。"""
    hits = []
    for f in root.rglob("*.md"):
        if any(x in f.parts for x in ("notes", ".git", "dist", "logs")):
            continue
        for i, line in enumerate(read(f).split("\n"), 1):
            if "<" not in line:
                continue
            # 排除"占位符规则"这句说明本身（它就是要讲尖括号的）
            if "占位符" in line:
                continue
            # 排除真正的 HTML 标签：标签名后必须跟空格、/ 或 >（收紧，防 <a@b> 被误放）
            if re.search(r"</?[a-zA-Z][a-zA-Z0-9]*(\s[^>]*)?/?>", line):
                continue
            if "<!--" in line:
                continue
            m = re.search(r"<[^<>\n]{1,40}>", line)
            if not m:
                continue
            # `<YYYYMMDD>` / `<20261020>` 是日期写法，不是占位符
            if re.fullmatch(r"<(?:YYYYMMDD|\d{8})>", m.group(0)):
                continue
            # `<name@host>` 是 git 身份的标准写法（Name <email>），不是占位符
            if re.fullmatch(r"<[^<>@\s]+@[^<>@\s]+>", m.group(0)):
                continue
            hits.append(f"{f.relative_to(root)}:{i}")
    if hits:
        bad("占位符", f"{len(hits)} 处残留：" + "；".join(hits[:6]))
    else:
        ok("占位符", "无残留")


def check_root_clean(root: Path) -> None:
    """根目录不放产物（只允许骨架文档 / 门面 / 配置 / 目录）。"""
    extra = []
    for f in root.iterdir():
        if f.is_dir() or f.name.startswith("."):
            continue
        if f.name in ROOT_ALLOWED:
            continue
        extra.append(f.name)
    if extra:
        bad("根目录", "有产物未归位：" + "、".join(extra[:6]))
    else:
        ok("根目录", "只住骨架文档与配置")


def check_dir_names(root: Path) -> None:
    """骨架层目录名英文小写。"""
    wrong = []
    for d in root.iterdir():
        if not d.is_dir() or d.name.startswith("."):
            continue
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", d.name):
            wrong.append(d.name)
    if wrong:
        bad("目录命名", "非英文小写：" + "、".join(wrong[:6]))
    else:
        ok("目录命名", "骨架层均英文小写")


def check_tables(root: Path) -> None:
    problems = []
    for f in root.rglob("*.md"):
        if any(x in f.parts for x in (".git", "dist", "notes")):
            continue
        in_code, header = False, None
        for i, line in enumerate(read(f).split("\n"), 1):
            s = line.strip()
            if s.startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            if not s.startswith("|"):
                header = None
                continue
            if set(s) <= set("|-: "):
                continue
            cells = s.replace("\\|", "\x00").strip("|").split("|")
            if header is None:
                header = len(cells)
            elif len(cells) != header:
                problems.append(f"{f.relative_to(root)}:{i}")
    if problems:
        bad("表格列数", f"{len(problems)} 处：" + "；".join(problems[:6]))
    else:
        ok("表格列数", "全部对齐")


def check_stage_route(root: Path) -> None:
    p = root / "MEMORY.md"
    if not p.exists():
        bad("阶段路线", "MEMORY.md 不存在")
        return
    text = read(p)
    if "阶段路线" in text:
        ok("阶段路线", "MEMORY.md 已记一条")
    else:
        bad("阶段路线", "MEMORY.md 里没有「阶段路线」那条 —— 下会话不知道项目在哪个阶段")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".", help="项目根目录")
    ap.add_argument("--quiet", action="store_true", help="只打印失败项")
    args = ap.parse_args()
    root = Path(args.root).resolve()

    check_core_docs(root)
    check_order_table(root)
    check_placeholders(root)
    check_root_clean(root)
    check_dir_names(root)
    check_tables(root)
    check_stage_route(root)

    failed = 0
    for passed, name, detail in results:
        if passed and args.quiet:
            continue
        print(f"[{'PASS' if passed else 'FAIL'}] {name:8s}  {detail}")
        if not passed:
            failed += 1

    print()
    if failed:
        print(f"{failed} 项未通过（共 {len(results)} 项）")
        return 1
    print(f"全部通过（{len(results)} 项）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
