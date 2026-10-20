#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""项目骨架自检（可选工具）。由 project-bootstrap 提供。

**什么时候用**：项目按 skill 立完骨架后、或每次较大改动收尾时，想确认"文档没失真"就跑一次。
**怎么用**：把本文件复制到项目的 `engineering/check_project.py`，然后

    python engineering/check_project.py .
    python engineering/check_project.py . --quiet     # 只报失败项

退出码：0 = 全过；1 = 有失败项。

它查十件事 —— 都是"靠人记会漏"的那类：
  1. 五份骨架文档齐不齐
  2. `.gitignore` 在不在（立项必备）
  3. AGENTS.md 顺序表里标 ☑ 的产物，磁盘上是否真的存在
  4. **反向**：磁盘上已有、表里却还是 ☐ 的（状态列失真）
  5. 落盘后有没有残留占位符 `<…>`（跳过代码块、比较符号、日期、邮箱）
  6. 根目录有没有住着产物
  7. 骨架层目录名是否英文小写、是否在成分表白名单里（`scripts/` 已退休）
  8. 文档里点名的内部路径是否指向真实存在的文件
  9. Markdown 表格列数一致
 10. MEMORY.md §2 有没有"阶段路线"那一条
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

# 骨架层允许的目录名（成分表白名单）
SKELETON_DIRS = {
    "content", "engineering", "docs", "notes", "assets", "models",
    "dist", "release", "archive", "logs", "templates", "skills", "src", "tests",
}

# 已退休的目录名
RETIRED_DIRS = {"scripts"}

# ---- skill 本体仓库模式（--skill）：本仓库不是被 skill 管理的项目，是 skill 自己 ----
SKILL_MODE = False
SKILL_ROOT_ALLOWED = {"SKILL.md", "LICENSE", ".gitattributes"}
SKILL_EXTRA_DIRS = {"references", "tools"}

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


def check_gitignore(root: Path) -> None:
    p = root / ".gitignore"
    if not p.exists():
        bad(".gitignore", "不存在 —— 立项必备件，logs/ 与平台目录会进库")
        return
    text = read(p)
    if len(text.strip()) < 20:
        bad(".gitignore", f"只有 {len(text.strip())} 字节，像是空壳")
    else:
        ok(".gitignore", f"{len(text.splitlines())} 行")


def _order_rows(root: Path) -> list[tuple[str, str]]:
    """解析 AGENTS.md §三 顺序表，返回 [(产物名, 状态单元格)]。"""
    p = root / "AGENTS.md"
    if not p.exists():
        return []
    lines = read(p).split("\n")
    start = None
    for i, l in enumerate(lines):
        if "产物长出来的顺序" in l:
            start = i
            break
    if start is None:
        return []

    rows, started = [], False
    for l in lines[start:]:
        s = l.strip()
        if s.startswith("|"):
            if not started:
                started = True
                continue
            if set(s) <= set("|-: "):
                continue
            cells = [c.strip() for c in s.strip("|").split("|")]
            if len(cells) >= 4:
                rows.append((cells[0].replace("`", "").strip(), cells[-1]))
        elif started:
            break
    return rows


def _tokens(name: str) -> list[str]:
    out = []
    for t in name.replace("`", "").split():
        t = t.strip("*")
        if t and t not in ("/",):
            out.append(t)
    return out


def check_order_table(root: Path) -> None:
    rows = _order_rows(root)
    if not rows:
        bad("顺序表", "AGENTS.md 里找不到「产物长出来的顺序」表")
        return

    wrong_ok = [t for n, st in rows if "☑" in st for t in _tokens(n) if not (root / t).exists()]
    if wrong_ok:
        bad("顺序表", "标 ☑ 但不存在：" + "、".join(wrong_ok[:6]))
        return
    ok("顺序表", f"{len(rows)} 行，☑ 的都在")


def check_order_reverse(root: Path) -> None:
    """反向：磁盘上已有、表里却还是 ☐ —— 状态列失真的另一半。"""
    rows = _order_rows(root)
    if not rows:
        return
    stale = []
    for name, st in rows:
        if "☑" in st:
            continue
        for t in _tokens(name):
            if (root / t).exists():
                stale.append(t)
                break
    if stale:
        bad("状态回填", "磁盘已有但表里还是 ☐：" + "、".join(stale[:6]) + " —— 把 ☐ 改成 ☑")
    else:
        ok("状态回填", "无「已有却标待建」")


def _in_fence(lines: list[str]) -> list[bool]:
    """标出每一行是否在围栏代码块内。"""
    flags, inside = [], False
    for l in lines:
        if l.strip().startswith("```"):
            flags.append(True)   # 围栏行本身也算"块内"
            inside = not inside
            continue
        flags.append(inside)
    return flags


def check_placeholders(root: Path) -> None:
    """落盘后不应残留 <…> 占位符（跳过代码块 / 比较符号 / 日期 / 邮箱 / HTML）。"""
    hits = []
    for f in root.rglob("*.md"):
        parts = f.relative_to(root).parts
        if any(x in parts for x in ("notes", ".git", "dist", "logs")):
            continue
        # 验收记录 / 变更记录是按版本累积的历史，里面的示例引用不算残留
        if f.name in ("ACCEPTANCE.md", "CHANGELOG.md"):
            continue
        # 只豁免模板目录（模板天生有占位符）；references 下的正文照样查
        if SKILL_MODE and parts[:2] == ("references", "templates"):
            continue
        lines = read(f).split("\n")
        fences = _in_fence(lines)
        for (i, line), in_fence in zip(enumerate(lines, 1), fences):
            if in_fence or "<" not in line:
                continue
            # "占位符规则"这句是在讲尖括号本身
            if "占位符" in line:
                continue
            # 真 HTML 标签：标签名后必须跟空格 / / 或 >
            if re.search(r"</?[a-zA-Z][a-zA-Z0-9]*(\s[^>]*)?/?>", line):
                continue
            if "<!--" in line:
                continue
            m = re.search(r"<[^<>\n]{1,40}>", line)
            if not m:
                continue
            s = m.group(0)
            # 日期 / 邮箱
            if re.fullmatch(r"<(?:YYYYMMDD|\d{8})>", s):
                continue
            if re.fullmatch(r"<[^<>@\s]+@[^<>@\s]+>", s):
                continue
            # 比较符号：`< 80` / `<80` / `> 80` 这类（设备参数、阈值常这么写）
            if re.match(r"<[ ]?\d", s) or re.match(r"<[ ]?[≥≤>]", s):
                continue
            hits.append(f"{f.relative_to(root)}:{i}")
    if hits:
        bad("占位符", f"{len(hits)} 处残留：" + "；".join(hits[:6]))
    else:
        ok("占位符", "无残留")


def check_root_clean(root: Path) -> None:
    allowed = ROOT_ALLOWED | (SKILL_ROOT_ALLOWED if SKILL_MODE else set())
    extra = [
        f.name for f in root.iterdir()
        if f.is_file() and not f.name.startswith(".") and f.name not in allowed
    ]
    if extra:
        bad("根目录", "有产物未归位：" + "、".join(extra[:6]))
    else:
        ok("根目录", "只住骨架文档与配置")


def check_dir_names(root: Path) -> None:
    bad_name, unknown = [], []
    for d in root.iterdir():
        if not d.is_dir() or d.name.startswith("."):
            continue
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", d.name):
            bad_name.append(d.name)
        elif d.name in RETIRED_DIRS:
            bad_name.append(f"{d.name}（已退休，辅助脚本进 engineering/）")
        elif d.name not in (SKELETON_DIRS | (SKILL_EXTRA_DIRS if SKILL_MODE else set())):
            unknown.append(d.name)
    if bad_name:
        bad("目录命名", "不合规：" + "、".join(bad_name[:6]))
    elif unknown:
        bad("目录命名", "不在成分表白名单：" + "、".join(unknown[:6]) + " —— 先查成分表，确需新增就登记进 AGENTS.md §三")
    else:
        ok("目录命名", "均英文小写且在成分表内")


def check_refs(root: Path) -> None:
    """文档里点名的内部路径（带扩展名）必须真实存在。

    skill 仓库模式不跳过 —— 只是多认一个基准：`references/` 下的文件，
    相对路径既可能从项目根算，也可能从 `references/` 算。
    """
    bases = [root, root / "references"] if SKILL_MODE else [root]
    pat = re.compile(
        r"`((?:docs|notes|engineering|content|assets|models|templates|skills|src|tests|dist|release|archive|logs)/[^\s`]+\.(?:md|py|html|css|js|json|yaml|yml|xlsx|csv))`"
    )
    missing = []
    for f in root.rglob("*.md"):
        parts = f.relative_to(root).parts
        if any(x in parts for x in (".git", "dist", "logs", "notes")):
            continue
        if f.name in ("ACCEPTANCE.md", "CHANGELOG.md"):
            continue
        for m in pat.finditer(read(f)):
            rel = m.group(1)
            # 通配符 / 命名模式（docs/{名称}_{YYYYMMDD}.html、docs/*.html）不是真实引用
            if re.search(r"[*{}<>]|YYYY", rel):
                continue
            # skill 仓库模式：engineering/ 开头的引用是在描述"项目侧该有什么"，不是本仓库的文件
            if SKILL_MODE and rel.startswith("engineering/"):
                continue
            if not any((b / rel).exists() for b in bases):
                missing.append(f"{f.relative_to(root)} → {rel}")
    if missing:
        bad("引用可达", f"{len(missing)} 处指向不存在的文件：" + "；".join(sorted(set(missing))[:6]))
    else:
        ok("引用可达", "文档点名的内部路径都在")


def check_tables(root: Path) -> None:
    problems = []
    for f in root.rglob("*.md"):
        if any(x in f.parts for x in (".git", "dist", "notes")):
            continue
        lines = read(f).split("\n")
        fences = _in_fence(lines)
        header = None
        for (i, line), in_fence in zip(enumerate(lines, 1), fences):
            if in_fence:
                continue
            s = line.strip()
            if not s.startswith("|"):
                header = None
                continue
            if set(s) <= set("|-: "):
                continue
            cells = s.replace("\\|", "\x00").strip("|").split("|")
            if header is None:
                header = len(cells)
            elif len(cells) != header:
                problems.append(f"{f.relative_to(root)}:{i}（{len(cells)} vs {header} 列；代码里的 | 请写成 \\|）")
    if problems:
        bad("表格列数", f"{len(problems)} 处：" + "；".join(problems[:6]))
    else:
        ok("表格列数", "全部对齐")


def check_stage_route(root: Path) -> None:
    p = root / "MEMORY.md"
    if not p.exists():
        bad("阶段路线", "MEMORY.md 不存在")
        return
    if "阶段路线" in read(p):
        ok("阶段路线", "MEMORY.md 已记一条")
    else:
        bad("阶段路线", "MEMORY.md 里没有「阶段路线」那条 —— 下会话不知道项目在哪个阶段")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=".", help="项目根目录")
    ap.add_argument("--quiet", action="store_true", help="只打印失败项")
    ap.add_argument("--skill", action="store_true", help="skill 本体仓库模式（豁免 SKILL.md / references / tools 等特有结构）")
    args = ap.parse_args()
    global SKILL_MODE
    root = Path(args.root).resolve()
    SKILL_MODE = args.skill
    if SKILL_MODE and not (root / "SKILL.md").exists():
        print("[FAIL] --skill 模式要求根目录有 SKILL.md —— 这不是 skill 本体仓库，去掉该参数")
        return 1

    check_core_docs(root)
    check_gitignore(root)
    check_order_table(root)
    check_order_reverse(root)
    check_placeholders(root)
    check_root_clean(root)
    check_dir_names(root)
    check_refs(root)
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
