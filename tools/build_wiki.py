# -*- coding: utf-8 -*-
"""Build a complete, source-linked MediaWiki XML dump for the three Apostle mods.

Only the Python standard library is used. Run from any directory with -I:
    python -I tools/build_wiki.py
The mod is read-only. No source data is edited.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
WORKSHOP = Path(r"D:\Steam\steamapps\workshop\content\718670")
GAME = Path(r"D:\Steam\steamapps\common\Cultist Simulator\cultistsimulator_Data\StreamingAssets\content")
MODS = {
    "contemnant": {"folder": "3445157833", "zh": "蔑世使徒", "en": "Apostle Contemnant", "year": "1944", "region": "德国"},
    "proterant": {"folder": "3171408151", "zh": "破军使徒", "en": "Apostle Proterant", "year": "1943", "region": "意大利"},
    "obdurant": {"folder": "2944178812", "zh": "坚毅使徒", "en": "Apostle Obdurant", "year": "1941", "region": "苏联"},
}
KINDS = ("elements", "recipes", "decks", "verbs", "legacies", "endings", "achievements")
KIND_ZH = {"elements": "卡牌", "recipes": "行动", "decks": "牌组", "verbs": "行动槽",
           "legacies": "传承", "endings": "结局", "achievements": "成就"}
FIELD_ZH = {
    "id": "内部 ID", "label": "名称", "description": "描述", "startdescription": "开始文本",
    "actionid": "行动槽", "icon": "图标", "image": "图片", "aspects": "性相", "requirements": "槽内要求",
    "extantreqs": "场上要求", "slots": "槽位", "slot": "初始槽位", "effects": "产出",
    "deckeffects": "抽取牌组", "linked": "后续行动", "alt": "额外／替代行动", "warmup": "持续时间",
    "craftable": "可主动启动", "lifetime": "时限", "decayTo": "时限结束后变为", "decayt o": "时限结束后变为",
    "xtriggers": "触发转变", "mutations": "性相变化", "internaldeck": "内置牌组", "purge": "移除",
    "expulsion": "弹出", "haltverb": "终止行动槽", "induces": "结局", "ending": "结局",
    "spec": "牌组构成", "draws": "抽取数", "defaultcard": "默认卡牌", "resetonexhaustion": "抽尽后重置",
    "unique": "唯一", "uniquenessgroup": "唯一性组", "resaturate": "重复播放消耗动画",
    "hintonly": "仅提供提示", "burnimage": "进程图片", "playAudioTrack": "播放音乐", "BGmusic": "背景音乐",
    "flavour": "结局类型", "achievements": "成就", "isHidden": "隐藏", "isAspect": "作为性相",
    "noartneeded": "不需图片", "maxUnique": "最大独立数", "spontaneous": "自动生成",
    "availableWithoutEndingMatch": "无需前置结局", "newstart": "可作为新开局", "startingverbid": "初始行动槽",
    "fromending": "前置结局", "statusbarelements": "状态栏元素", "tablecoverimage": "桌面底图",
    "overrideBGmusic": "覆盖背景音乐", "quotes": "载入引言", "menuVisualsOverride": "主菜单视觉配置",
    "category": "成就分类", "isCategory": "为成就分类", "descriptionLocked": "未解锁描述",
    "descriptionUnlocked": "已解锁描述", "unlockMessage": "解锁信息", "iconLocked": "未解锁图标",
    "iconUnlocked": "已解锁图标", "audio": "音频", "slot": "槽位", "slot$append": "追加槽位",
}
PRINCIPLES = {"edge": "刃", "winter": "冬", "heart": "心", "grail": "杯", "moth": "蛾",
              "lantern": "灯", "forge": "铸", "knock": "启", "secret histories": "秘史", "secrethistories": "秘史"}
TEXT_FIELDS = {"label", "description", "startdescription", "descriptionLocked", "descriptionUnlocked", "unlockMessage", "comments"}
ENGLISH_COPY = {"requirements", "extantreqs", "effects", "slots", "slot", "linked", "alt", "internaldeck",
                "deckeffects", "induces", "haltverb", "purge", "expulsion", "mutations", "xtriggers",
                "statusbarelements", "spec", "quotes", "BGmusic"}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def scalar(v):
    if isinstance(v, bool):
        return "是" if v else "否"
    return str(v)


def safe(value: str) -> str:
    """Keep source text verbatim but neutralize wiki/HTML markup."""
    return html.escape(str(value), quote=False).replace("|", "&#124;")


def rich_text(value: str) -> str:
    """Render only the game's presentational i/b tags; escape everything else."""
    parts = re.split(r"(</?[ib]>)", str(value))
    return "".join(part if part in ("<i>", "</i>", "<b>", "</b>") else safe(part) for part in parts)


def clean_text(value: str) -> str:
    return re.sub(r"</?i>", "", str(value)).strip()


def attr(v):
    return html.escape(str(v), quote=True)


def safe_filename(s):
    return re.sub(r'[<>:"/\\|?*]', "_", s)


def parse_loose_value(raw):
    raw = raw.strip()
    if raw in ("true", "false"):
        return raw == "true"
    if raw in ("null", "Null"):
        return None
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    try:
        if re.fullmatch(r"-?\d*\.\d+", raw):
            return float(raw)
    except ValueError:
        pass
    return raw


def restore_json(path: Path):
    """Add commas the game's permissive loader accepts between members/items.

    Only commas between adjacent parsed values are inserted; string contents and
    all values stay intact. Duplicate keys are retained as _2, _3 rather than
    silently discarded. Fails loudly for genuinely unrecognized JSON.
    """
    text = path.read_text(encoding="utf-8-sig")
    out = []
    i = 0
    state = "value"
    pairs = re.compile(r'("(?:[^"\\]|\\.)*")\s*:')
    while i < len(text):
        ch = text[i]
        if ch == '"':
            start = i
            i += 1
            while i < len(text):
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == '"':
                    i += 1
                    break
                i += 1
            token = text[start:i]
            token = re.sub(r"[\x00-\x1f]", lambda match: "\\u%04x" % ord(match.group()), token)
            out.append(token)
            j = i
            while j < len(text) and text[j].isspace():
                j += 1
            if state == "value" and j < len(text) and text[j] == ":":
                state = "key"
            continue
        if ch in "{}[]:,":
            out.append(ch)
            if ch == ":":
                state = "value"
            elif ch == "{":
                state = "key"
            elif ch == "[":
                state = "array_start"
            elif ch in "}]":
                state = "after"
            elif ch == ",":
                state = "key"
            i += 1
            continue
        if ch.isspace():
            # A newline followed by a quoted key means an omitted comma.
            j = i
            while j < len(text) and text[j].isspace():
                j += 1
            if "\n" in text[i:j] or "\r" in text[i:j]:
                if state == "after" and j < len(text) and text[j] not in "}]":
                    if pairs.match(text, j):
                        out.append(",")
                        state = "key"
                    elif text[j] == "{":
                        out.append(",")
                        state = "key"
                    elif text[j] == '"':
                        # An unlabelled value is only valid as an array item.
                        out.append(",")
                        state = "value"
            i = j
            continue
        j = i
        while j < len(text) and not text[j].isspace() and text[j] not in "{}[],:":
            j += 1
        token = text[i:j]
        if token.startswith("//"):
            i = j
            continue
        # Validate JSON scalars (case variations used by a few mod files).
        if token.lower() in ("true", "false", "null"):
            token = token.lower()
        elif not re.fullmatch(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?", token):
            raise ValueError(f"{path}: unsupported JSON token {token!r}")
        out.append(token)
        i = j
        state = "after"

    def unique_pairs(items):
        seen = Counter()
        result = []
        for key, value in items:
            seen[key] += 1
            result.append((key if seen[key] == 1 else f"{key}_{seen[key]}", value))
        return dict(result)

    raw = re.sub(r",(?=\s*[}\]])", "", "".join(out))
    try:
        return json.loads(raw, object_pairs_hook=unique_pairs)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: {exc}; repaired JSON around: {raw[max(0,exc.pos-80):exc.pos+80]!r}") from exc


class Wiki:
    def __init__(self):
        self.pages = []
        self.titles = set()
        self.title_counts = Counter()
        self.stats = Counter()

    def add(self, title, text, comment="由本地 Mod 数据生成", append=False):
        if title in self.titles:
            if append:
                for page in reversed(self.pages):
                    if page["title"] == title:
                        page["text"] += "\n" + text
                        return
            raise ValueError(f"Duplicate page: {title}")
        self.titles.add(title)
        self.pages.append({"title": title, "text": text.strip() + "\n", "comment": comment})
        self.stats[title.split(":", 1)[0]] += 1

    def export(self, path):
        now = datetime.now(timezone.utc).isoformat()
        ns = "http://www.mediawiki.org/xml/export-0.11/"
        root = ET.Element("siteinfo")
        for key, val in [("sitename", "三刃使徒 Wiki"), ("dbname", "sanren"), ("base", "http://localhost:8080/"),
                         ("generator", "三刃使徒本地数据导入器"), ("case", "first-letter")]:
            ET.SubElement(root, key).text = val
        parts = [f'<?xml version="1.0" encoding="utf-8"?>\n<mediawiki xmlns="{ns}" version="0.11" xml:lang="zh-cn">\n']
        parts.append(ET.tostring(root, encoding="unicode") + "\n")
        for n, page in enumerate(self.pages, 1):
            title = page["title"]
            namespace = 0
            if ":" in title:
                prefix = title.split(":", 1)[0]
                namespace = {"MediaWiki": 8, "模板": 10, "原始数据": 3000, "项目": 4}.get(prefix, 0)
            else:
                namespace = 0
            p = ET.Element("page")
            ET.SubElement(p, "title").text = title
            ET.SubElement(p, "ns").text = str(namespace)
            ET.SubElement(p, "id").text = str(n)
            rev = ET.SubElement(p, "revision")
            ET.SubElement(rev, "id").text = str(n)
            ET.SubElement(rev, "timestamp").text = now
            contrib = ET.SubElement(rev, "contributor")
            ET.SubElement(contrib, "username").text = "SanrenImporter"
            ET.SubElement(rev, "comment").text = page["comment"]
            model = ET.SubElement(rev, "model"); model.text = "wikitext"
            ET.SubElement(rev, "format").text = "text/x-wiki"
            t = ET.SubElement(rev, "text", {"xml:space": "preserve"}); t.text = page["text"]
            parts.append(ET.tostring(p, encoding="unicode") + "\n")
        parts.append("</mediawiki>\n")
        write_text(path, "".join(parts))


class Builder:
    def __init__(self):
        self.wiki = Wiki()
        self.title_counts = Counter()
        self.mods = {}
        self.base = {}
        self.titles = {}
        self.global_records = {}
        self.references = []
        self.orphan_titles = {}
        self.locale_overrides = []
        self.aspect_owners = defaultdict(list)
        self.reports = Counter()
        self.all_images = {}

    def title_for(self, mod, kind, rid):
        return self.titles.get((mod, kind, rid))

    def register(self, mod, kind, rid, title):
        if (mod, kind, rid) in self.titles:
            raise ValueError(f"Duplicate ID {mod}/{kind}/{rid}")
        self.titles[(mod, kind, rid)] = title
        self.global_records.setdefault((kind, rid), []).append((mod, title))

    def ref(self, mod, rid, label=None, kind=None):
        if not rid:
            return "—"
        kinds = [kind] if kind else KINDS
        title = None
        for k in kinds:
            if (mod, k, rid) in self.titles:
                title = self.titles[(mod, k, rid)]
                break
        if title is None and (mod, "elements", rid) in self.titles:
            title = self.titles[(mod, "elements", rid)]
        if title:
            if label and clean_text(label) == safe(title.split(":", 1)[1]):
                return f"[[{title}]]"
            return f"[[{title}|{safe(label or title.split(':', 1)[1])}]]"
        if kind == "aspects" or (rid in self.aspect_owners and kind is None):
            return f"[[性相:{safe(label or rid)}]]"
        if rid in self.base:
            base = self.base[rid]
            label = safe(label or base.get("label") or rid)
            return f"{label}<small>（本体：<code>{safe(rid)}</code>）</small>"
        return f"{safe(label or rid)}<small>（<code>{safe(rid)}</code>）</small>"

    def read_mods(self):
        for mod, info in MODS.items():
            root = WORKSHOP / info["folder"]
            records = {k: {} for k in KINDS}
            english = {k: {} for k in KINDS}
            locales = {k: {} for k in KINDS}
            sources = {k: {} for k in KINDS}
            all_json = list(root.rglob("*.json"))
            for path in all_json:
                data = restore_json(path)
                for kind in KINDS:
                    if not isinstance(data, dict) or kind not in data:
                        continue
                    for rec in data[kind]:
                        if not isinstance(rec, dict) or not rec.get("id"):
                            self.reports[f"{mod}:missing_id"] += 1
                            continue
                        rid = rec["id"]
                        is_locale = "loc" in path.relative_to(root).parts
                        target = locales if is_locale else records
                        if rid in target[kind]:
                            # These mods ship a Russian loc in addition to Chinese.
                            # Locales share IDs by design; do not treat them as
                            # duplicate content records or allow Russian to win.
                            if is_locale:
                                if "loc_zh-hans" in path.parts or "loc_ru" not in path.parts:
                                    locales[kind][rid] = rec
                                continue
                            self.reports[f"{mod}:{kind}:duplicate_content_id"] += 1
                        target[kind][rid] = rec
                        sources[kind][rid] = path.relative_to(root).as_posix()
                        if not is_locale:
                            english[kind][rid] = rec
            synopsis = restore_json(root / "synopsis.json")
            self.mods[mod] = {"root": root, "records": records, "english": english,
                              "locales": locales, "sources": sources, "synopsis": synopsis,
                              "json_count": len(all_json)}
            # Match all available locales. Chinese only replaces text, never mechanics.
            for kind in KINDS:
                for rid, rec in records[kind].items():
                    loc = locales[kind].get(rid, {})
                    for key, value in loc.items():
                        if key in TEXT_FIELDS or key.endswith("$clear"):
                            rec[key] = value
                        elif key not in rec:
                            rec[key] = value
                        elif rec[key] != value:
                            self.reports[f"{mod}:{kind}:numeric_locale_override"] += 1
                            self.locale_overrides.append({"mod":mod,"kind":kind,"id":rid,"field":key,
                                "content":rec[key],"localization":value,
                                "source":path.relative_to(root).as_posix()})
                    if loc:
                        rec["_has_zh"] = True
            for img in (root / "images").rglob("*.png"):
                key = img.stem.lower()
                if key in self.all_images:
                    continue
                self.all_images[key] = (mod, img)
            for audio in (root / "audio").rglob("*.mp3"):
                self.all_images[audio.stem.lower()] = (mod, audio)

    def read_base(self):
        for root_name, loc_name in [("core", "loc_zh-hans")]:
            for path in (GAME / root_name).rglob("*.json"):
                try:
                    data = restore_json(path)
                except (ValueError, json.JSONDecodeError):
                    continue
                if not isinstance(data, dict):
                    continue
                for kind in ("elements", "verbs", "recipes", "endings", "legacies", "decks"):
                    for rec in data.get(kind, []):
                        if rec.get("id"):
                            self.base.setdefault(rec["id"], rec)
            for path in (GAME / loc_name).rglob("*.json"):
                try:
                    data = restore_json(path)
                except (ValueError, json.JSONDecodeError):
                    continue
                if not isinstance(data, dict):
                    continue
                for kind in ("elements", "verbs", "recipes", "endings", "legacies", "decks"):
                    for rec in data.get(kind, []):
                        if rec.get("id") in self.base:
                            for key in TEXT_FIELDS:
                                if key in rec:
                                    self.base[rec["id"]][key] = rec[key]

    def allocate_titles(self):
        for mod, info in MODS.items():
            records = self.mods[mod]["records"]
            for kind in KINDS:
                used = Counter()
                for rid, rec in records[kind].items():
                    label = re.sub(r"<[^>]*>", "", clean_text(rec.get("label") or rid)).replace("[", "［").replace("]", "］")
                    if "#PREVIOUSCHARACTERNAME#" in label:
                        label = label.replace("#PREVIOUSCHARACTERNAME#", "前任流亡者")
                    if kind == "endings":
                        label = re.sub(r"<[^>]*>", "", clean_text(rec.get("label") or rid)).replace("[", "［").replace("]", "］")
                    if "#PREVIOUSCHARACTERNAME#" in label:
                        label = label.replace("#PREVIOUSCHARACTERNAME#", "前任流亡者")
                    used[label] += 1
                    title = f"{info['zh']}:{label}"
                    self.title_counts[title] += 1
                    if used[label] > 1 or self.title_counts[title] > 1:
                        title = f"{info['zh']}:{label} ({rid})"
                    self.register(mod, kind, rid, title)
                    for aspect, level in rec.get("aspects", {}).items():
                        if isinstance(level, (int, float)) and level > 0:
                            self.aspect_owners[aspect].append((mod, kind, rid))

    def pretty(self, v):
        if isinstance(v, dict):
            return json.dumps(v, ensure_ascii=False, indent=2)
        if isinstance(v, list):
            return json.dumps(v, ensure_ascii=False, indent=2)
        return scalar(v)

    def raw_page(self, mod, kind, rid, rec, title):
        src = self.mods[mod]["sources"][kind][rid]
        return ("<noinclude>本页由导入器从原始 JSON 生成，包含源文件中未被简中本地化覆盖的完整字段。"
                f"主条目：[[{self.title_for(mod,kind,rid)}]]。</noinclude>\n"
                f"<source lang=\"json\">{safe(json.dumps(rec, ensure_ascii=False, indent=2))}</source>\n"
                f"[[分类:原始数据]][[分类:{MODS[mod]['zh']}·原始数据]]\n"
                f"数据文件：<code>{safe(src)}</code>")

    def aspects(self, mod, aspects):
        if not isinstance(aspects, dict):
            return self.pretty(aspects)
        items = []
        for key, val in aspects.items():
            name = PRINCIPLES.get(key, key)
            items.append(f"{self.ref(mod,key,name,kind='aspects')} {scalar(val)}")
        return "；".join(items)

    def media_link(self, icon, size=160, caption=None):
        """Return a local thumbnail linked to the file description for preview.

        Mod/ was never a registered MediaWiki namespace; it created broken links.
        Missing base-game art is explained rather than rendered as a red link.
        """
        if not icon:
            return ""
        if isinstance(icon, str) and icon.lower().endswith(".mp3"):
            return f'[[文件:{safe_filename(icon)}|{safe(caption or icon)}]]'
        icon = re.sub(r"^Mod/", "", str(icon))
        if icon.lower() not in self.all_images:
            return f'<span class="missing-art">Mod 未提供此卡图；图标 ID：<code>{safe(icon)}</code></span>'
        cap = f"|{safe(caption)}" if caption else ""
        return f'[[文件:{safe_filename(icon)}.png|缩略图|{size}px|class=card-art{cap}]]'

    def element_page(self, mod, rid, e):
        title = self.title_for(mod, "elements", rid)
        display = title.split(":", 1)[1]
        en = self.mods[mod]["english"]["elements"].get(rid, {})
        source = self.mods[mod]["sources"]["elements"][rid]
        icon = e.get("icon") or rid
        img = self.all_images.get(icon.lower())
        cat = self.card_categories(mod, e)
        s = [f"{{{{消歧义提示|{MODS[mod]['zh']}}}}}" if len(self.global_records[("elements", rid)]) > 1 else "",
             '<table class="infobox sanren-card"><tr><th colspan="2">' + safe(display) + '</th></tr>',
             f'<tr><td colspan="2" class="card-image">{self.media_link(icon,160,display)}</td></tr>' if img else "",
             f'<tr><th>Mod</th><td>[[{MODS[mod]["zh"]}]]</td></tr>',
             f'<tr><th>内部 ID</th><td><code>{safe(rid)}</code></td></tr>']
        if clean_text(en.get("label", "")) != clean_text(e.get("label", "")):
            s.append(f'<tr><th>英文原名</th><td>{safe(en.get("label",""))}</td></tr>')
        if e.get("aspects"):
            s.append(f'<tr><th>性相</th><td>{self.aspects(mod,e["aspects"])}</td></tr>')
        for key, zh in [("lifetime","时限（秒）"),("decayTo","时限结束"),("unique","唯一"),
                        ("uniquenessgroup","唯一性组"),("isHidden","隐藏"),("resaturate","重复消耗动画")]:
            if key in e:
                val = self.ref(mod,e[key]) if key == "decayTo" else self.pretty(e[key])
                s.append(f'<tr><th>{zh}</th><td>{val if key=="decayTo" else safe(val)}</td></tr>')
        s.append('</table>')
        if e.get("description"):
            s.append(f'<div class="flavour">{rich_text(e["description"]).replace(chr(10),"<br/>")}</div>')
        if e.get("xtriggers"):
            s.append("\n== 触发与转变 ==\n" + self.general_table(mod, {"xtriggers": e["xtriggers"]}))
        if e.get("slots"):
            s.append("\n== 槽位 ==\n" + self.slots_table(mod, e["slots"]))
        linked = self.element_relations(mod, rid)
        if linked:
            s.append("\n== 相关行动 ==\n" + "\n".join(f"* {x}" for x in linked))
        others = [(m,t) for m,t in self.global_records[("elements", rid)] if m != mod]
        if others:
            s.append("\n== 同名条目 ==\n" + "\n".join(f"* [[{t}|{MODS[m]['zh']}：{clean_text(self.mods[m]['records']['elements'][rid].get('label') or rid)}]]" for m,t in others))
        s.append("\n== 数据与来源 ==\n")
        if not e.get("_has_zh"):
            s.append("{{未翻译}}")
        s.append(f"本页优先展示 Mod 自带的简中本地化；机制字段来自英文原始数据。<br/>源文件：<code>{safe(source)}</code> · [[原始数据:元素/{safe_filename(mod + '__' + rid)}|查看完整 JSON]]。")
        for c in cat:
            s.append(f"[[分类:{MODS[mod]['zh']}·{c}]]")
        s.append(f"[[分类:{MODS[mod]['zh']}·卡牌]]")
        return "\n".join(x for x in s if x)

    def card_categories(self, mod, e):
        aspects = e.get("aspects", {})
        if not isinstance(aspects, dict):
            aspects = {}
        if e.get("isHidden"):
            return ["隐藏与机制卡牌"]
        for a, c in [("friend","盟友"),("foe","敌人"),("warzone","战区"),("location","地点"),
                     ("weapon","武器"),("lore","密传"),("supplies","补给"),("hindrance","阻碍"),
                     ("wound.eye","伤口与创伤"),("wound.ear","伤口与创伤"),("wound.hand","伤口与创伤"),
                     ("wound.leg","伤口与创伤"),("decision","决策"),("remnant","遗骸"),
                     ("contemplation","思考"),("legacyplotitem","剧情物品"),("memory","回忆")]:
            if a in aspects:
                return [c]
        return ["其他卡牌"]

    def element_relations(self, mod, rid):
        out = []
        for rec in self.mods[mod]["records"]["recipes"].values():
            found = []
            for field in ("requirements", "extantreqs", "effects", "deckeffects", "haltverb", "purge"):
                if rid in rec.get(field, {}):
                    found.append(FIELD_ZH[field])
            for slot in rec.get("slots", []):
                if not isinstance(slot, dict):
                    continue
                for field in ("required", "forbidden"):
                    if rid in slot.get(field, {}):
                        found.append(FIELD_ZH.get("slots","槽位"))
            if found:
                rt = self.title_for(mod,"recipes",rec["id"])
                out.append(f"[[{rt}|{safe(clean_text(rec.get('label') or rec['id']))}]]（{'、'.join(dict.fromkeys(found))}）")
        for d in self.mods[mod]["records"]["decks"].values():
            if rid in d.get("spec", []) or rid == d.get("defaultcard"):
                out.append(f"[[{self.title_for(mod,'decks',d['id'])}|{safe(d.get('label') or d['id'])}]]（牌组）")
        return out

    def general_table(self, mod, data):
        rows = []
        for key, val in data.items():
            if key.startswith("_") or key in TEXT_FIELDS or key == "id":
                continue
            zh = FIELD_ZH.get(key, key)
            if key == "aspects":
                value = self.aspects(mod,val)
            elif key in ("requirements","extantreqs","effects","deckeffects","haltverb","purge"):
                value = self.req_table(mod,val)
            elif key in ("slots",):
                value = self.slots_table(mod,val)
            elif key in ("linked","alt"):
                value = self.recipe_links(mod,val)
            elif key in ("internaldeck",):
                value = self.deck_embed(mod,val)
            elif key in ("decayTo","actionid"):
                value = self.ref(mod,val)
            elif isinstance(val, (dict,list)):
                value = f"<pre>{safe(self.pretty(val))}</pre>"
            else:
                value = safe(scalar(val)).replace("\n", "<br/>")
            rows.append(f'<tr><th>{safe(zh)}<br/><small><code>{safe(key)}</code></small></th><td>{value}</td></tr>')
        return '<table class="wikitable sanren-data"><tbody>' + "".join(rows) + '</tbody></table>' if rows else ""

    def req_table(self, mod, data):
        if not isinstance(data, dict):
            return safe(self.pretty(data))
        rows = []
        for rid, value in data.items():
            val = self.ref(mod,value,kind="aspects") if isinstance(value,str) else scalar(value)
            rows.append(f'<tr><td>{self.ref(mod,rid)}</td><td>{safe(val)}</td></tr>')
        return '<table class="wikitable compact"><tr><th>ID／性相</th><th>数量或阈值</th></tr>' + "".join(rows) + '</table>'

    def slots_table(self, mod, slots):
        if not isinstance(slots,list):
            return f"<pre>{safe(self.pretty(slots))}</pre>"
        out = []
        for slot in slots:
            if not isinstance(slot,dict):
                out.append(f"<pre>{safe(self.pretty(slot))}</pre>")
                continue
            out.append(f"<h4>{safe(slot.get('label') or slot.get('id') or '槽位')}</h4>")
            out.append(self.general_table(mod,slot))
        return "".join(out)

    def recipe_links(self, mod, links):
        if not isinstance(links,list):
            return f"<pre>{safe(self.pretty(links))}</pre>"
        rows = []
        for l in links:
            if not isinstance(l,dict):
                rows.append(f"<tr><td><pre>{safe(self.pretty(l))}</pre></td></tr>")
                continue
            rid = l.get("id")
            bits = []
            if "chance" in l: bits.append(f"概率 {l['chance']}%")
            if l.get("additional"): bits.append("额外执行")
            if l.get("expulsion"): bits.append("弹出：" + safe(self.pretty(l["expulsion"])))
            extra = {k:v for k,v in l.items() if k not in ("id","chance","additional","expulsion")}
            if extra: bits.append(f"<code>{safe(self.pretty(extra))}</code>")
            rows.append(f"<tr><td>{self.ref(mod,rid,kind='recipes')}</td><td>{'；'.join(bits) or '—'}</td></tr>")
        return '<table class="wikitable compact"><tr><th>行动</th><th>条件</th></tr>' + "".join(rows) + '</table>'

    def deck_embed(self, mod, deck):
        spec = deck.get("spec",[])
        counts = Counter(spec)
        out = self.general_table(mod,{k:v for k,v in deck.items() if k != "spec"})
        out += '<table class="wikitable compact"><tr><th>卡牌</th><th>张数</th></tr>'
        for rid, count in counts.items():
            out += f"<tr><td>{self.ref(mod,rid)}</td><td>{count}</td></tr>"
        return out + '</table>'

    def recipe_page(self, mod, rid, r):
        title = self.title_for(mod,"recipes",rid)
        display = title.split(":",1)[1]
        en = self.mods[mod]["english"]["recipes"].get(rid,{})
        s = [f'<table class="infobox"><tr><th colspan="2">{safe(display)}</th></tr>',
             f'<tr><th>Mod</th><td>[[{MODS[mod]["zh"]}]]</td></tr>',
             f'<tr><th>内部 ID</th><td><code>{safe(rid)}</code></td></tr>']
        if en.get("label") and en.get("label") != r.get("label"):
            s.append(f'<tr><th>英文原名</th><td>{safe(en["label"])}</td></tr>')
        if r.get("actionid"):
            s.append(f'<tr><th>行动槽</th><td>{self.ref(mod,r["actionid"],kind="verbs")}</td></tr>')
        for key,zh in [("warmup","持续时间（秒）"),("craftable","可主动启动"),("hintonly","仅提示")]:
            if key in r: s.append(f'<tr><th>{zh}</th><td>{safe(scalar(r[key]))}</td></tr>')
        s.append('</table>')
        if r.get("startdescription"):
            s.append(f'<div class="flavour"><strong>开始：</strong>{safe(r["startdescription"]).replace(chr(10),"<br/>")}</div>')
        if r.get("description"):
            s.append(f'<div class="flavour"><strong>完成：</strong>{safe(r["description"]).replace(chr(10),"<br/>")}</div>')
        s.append("\n== 条件与效果 ==\n" + self.general_table(mod,r))
        s.append("\n== 数据与来源 ==\n")
        if not r.get("_has_zh"): s.append("{{未翻译}}")
        src = self.mods[mod]["sources"]["recipes"][rid]
        s.append(f"源文件：<code>{safe(src)}</code> · [[原始数据:行动/{safe_filename(mod+'__'+rid)}|完整 JSON]]。负面数值表示移除；变量阈值与原始字段名并列展示，具体引擎执行语义以游戏为准。")
        s.append(f"[[分类:{MODS[mod]['zh']}·行动]]")
        if r.get("hintonly"): s.append(f"[[分类:{MODS[mod]['zh']}·提示行动]]")
        if r.get("craftable"): s.append(f"[[分类:{MODS[mod]['zh']}·可主动行动]]")
        return "\n".join(s)

    def deck_page(self, mod, rid, d):
        title = self.title_for(mod,"decks",rid)
        s = [f'<table class="infobox"><tr><th colspan="2">{safe(title.split(":",1)[1])}</th></tr>',
             f'<tr><th>Mod</th><td>[[{MODS[mod]["zh"]}]]</td></tr><tr><th>内部 ID</th><td><code>{safe(rid)}</code></td></tr>',
             f'<tr><th>抽尽后重置</th><td>{safe(scalar(d.get("resetonexhaustion",False)))}</td></tr></table>']
        if d.get("description"): s.append(f'<div class="flavour">{safe(d["description"])}</div>')
        counts = Counter(d.get("spec",[]))
        s.append("\n== 牌组构成 ==\n{| class=\"wikitable sortable\"\n! 卡牌 !! 张数 !! 理论单抽占比")
        for card,count in counts.items():
            s.append(f"|-\n| {self.ref(mod,card)} || {count} || {count/len(d['spec']):.2%}")
        s.append("|}")
        s.append("\n== 其他字段 ==\n" + self.general_table(mod,{k:v for k,v in d.items() if k not in ("spec","description")}))
        if d.get("defaultcard"):
            s.append(f"牌组为空或抽完且未重置时的默认卡牌：{self.ref(mod,d['defaultcard'])}。")
        s.append(f"\n源文件：<code>{safe(self.mods[mod]['sources']['decks'][rid])}</code> · [[原始数据:牌组/{safe_filename(mod+'__'+rid)}|完整 JSON]]。")
        if not d.get("_has_zh"): s.append("{{未翻译}}")
        s.append(f"[[分类:{MODS[mod]['zh']}·牌组]]")
        return "\n".join(s)

    def verb_page(self, mod, rid, v):
        title = self.title_for(mod,"verbs",rid)
        s = [f'<table class="infobox"><tr><th colspan="2">{safe(title.split(":",1)[1])}</th></tr>',
             f'<tr><th>Mod</th><td>[[{MODS[mod]["zh"]}]]</td></tr><tr><th>内部 ID</th><td><code>{safe(rid)}</code></td></tr></table>']
        if v.get("description"): s.append(f'<div class="flavour">{safe(v["description"]).replace(chr(10),"<br/>")}</div>')
        s.append("\n== 定义 ==\n" + self.general_table(mod,v))
        related = [r for r in self.mods[mod]["records"]["recipes"].values() if r.get("actionid") == rid]
        s.append(f"\n== 关联行动（{len(related)}） ==\n" + self.record_list(mod,"recipes",related))
        s.append(f"\n源文件：<code>{safe(self.mods[mod]['sources']['verbs'][rid])}</code> · [[原始数据:行动槽/{safe_filename(mod+'__'+rid)}|完整 JSON]]。")
        s.append(f"[[分类:{MODS[mod]['zh']}·行动槽]]")
        return "\n".join(s)

    def ending_page(self, mod, rid, e):
        title = self.title_for(mod,"endings",rid)
        image = e.get("image",rid)
        s = [f'<table class="infobox ending"><tr><th colspan="2">{safe(title.split(":",1)[1])}</th></tr>',
             f'<tr><td colspan="2">{self.media_link(image,260,title.split(":",1)[1])}</td></tr>',
             f'<tr><th>Mod</th><td>[[{MODS[mod]["zh"]}]]</td></tr><tr><th>内部 ID</th><td><code>{safe(rid)}</code></td></tr>']
        if e.get("flavour"): s.append(f'<tr><th>类型</th><td>{safe(e["flavour"])}</td></tr>')
        s.append('</table>')
        if e.get("description"): s.append(f'<div class="flavour ending-text">{rich_text(e["description"]).replace(chr(10),"<br/>")}</div>')
        s.append("\n== 达成行动 ==\n")
        reach = []
        for r in self.mods[mod]["records"]["recipes"].values():
            if self.contains_id(r.get("induces",{}),rid) or r.get("ending") == rid:
                reach.append(f"* {self.ref(mod,r['id'],r.get('label'),kind='recipes')}")
        s.extend(reach or ["* 未在本地行动数据中找到直接引用，可能由游戏本体或其他继承流程触发。"])
        s.append("\n== 其他字段 ==\n" + self.general_table(mod,{k:v for k,v in e.items() if k not in ("description","image")}))
        if e.get("BGmusic"):
            s.append(f"\n== 音频 ==\n{self.media_link(e['BGmusic'],caption='播放结局音乐')}")
        s.append(f"\n源文件：<code>{safe(self.mods[mod]['sources']['endings'][rid])}</code> · [[原始数据:结局/{safe_filename(mod+'__'+rid)}|完整 JSON]]。")
        s.append(f"[[分类:{MODS[mod]['zh']}·结局]]")
        return "\n".join(s)

    def contains_id(self, value, rid):
        if isinstance(value,dict): return rid in value or any(self.contains_id(v,rid) for v in value.values())
        if isinstance(value,list): return any(self.contains_id(v,rid) for v in value)
        return value == rid

    def achievement_page(self,mod,rid,a):
        title = self.title_for(mod,"achievements",rid)
        icon = a.get("iconUnlocked") or a.get("iconLocked") or rid
        s = [f'<table class="infobox"><tr><th colspan="2">{safe(title.split(":",1)[1])}</th></tr>',
             f'<tr><td colspan="2">{self.media_link(icon,96,title.split(":",1)[1])}</td></tr>',
             f'<tr><th>Mod</th><td>[[{MODS[mod]["zh"]}]]</td></tr><tr><th>内部 ID</th><td><code>{safe(rid)}</code></td></tr>',
             f'<tr><th>隐藏成就</th><td>{safe(scalar(a.get("isHidden",False)))}</td></tr></table>']
        for k,zh in [("descriptionLocked","未解锁"),("descriptionUnlocked","已解锁"),("unlockMessage","解锁信息")]:
            if a.get(k): s.append(f"\n== {zh} ==\n<div class=\"flavour\">{safe(a[k]).replace(chr(10),'<br/>')}</div>")
        s.append("\n== 其他字段 ==\n" + self.general_table(mod,{k:v for k,v in a.items() if k not in TEXT_FIELDS}))
        s.append(f"\n源文件：<code>{safe(self.mods[mod]['sources']['achievements'][rid])}</code> · [[原始数据:成就/{safe_filename(mod+'__'+rid)}|完整 JSON]]。")
        s.append(f"[[分类:{MODS[mod]['zh']}·成就]]")
        return "\n".join(s)

    def legacy_page(self,mod,rid,l):
        title = self.title_for(mod,"legacies",rid)
        s = [f'<table class="infobox legacy"><tr><th colspan="2">{safe(title.split(":",1)[1])}</th></tr>',
             f'<tr><td colspan="2">[[文件:{MODS[mod]["zh"]}_封面.png|260px]]</td></tr>',
             f'<tr><th>作者</th><td>{safe(self.mods[mod]["synopsis"].get("author",""))}</td></tr>',
             f'<tr><th>版本</th><td>{safe(self.mods[mod]["synopsis"].get("version",""))}</td></tr>',
             f'<tr><th>内部 ID</th><td><code>{safe(rid)}</code></td></tr></table>']
        for k,zh in [("description","简介"),("startdescription","开场")]:
            if l.get(k): s.append(f"\n== {zh} ==\n<div class=\"flavour\">{safe(l[k]).replace(chr(10),'<br/>')}</div>")
        s.append("\n== 开局与机制 ==\n" + self.general_table(mod,{k:v for k,v in l.items() if k not in TEXT_FIELDS}))
        for q in l.get("quotes",[]): s.append(f'<div class="flavour quote">{safe(q).replace(chr(10),"<br/>")}</div>')
        s.append(f"\n源文件：<code>{safe(self.mods[mod]['sources']['legacies'][rid])}</code> · [[原始数据:传承/{safe_filename(mod+'__'+rid)}|完整 JSON]]。")
        s.append(f"[[分类:{MODS[mod]['zh']}·传承]]")
        return "\n".join(s)

    def record_list(self,mod,kind,records):
        if not records: return "暂无记录。"
        lines = ['{| class="wikitable sortable sanren-index"',f"! 名称 !! 内部 ID !! 说明"]
        for r in sorted(records,key=lambda r:(clean_text(r.get("label") or r["id"]),r["id"])):
            rid = r["id"]
            text = clean_text(r.get("description") or r.get("startdescription") or r.get("label") or "")
            text = re.sub(r"<[^>]+>","",text).replace("\n"," ")
            if len(text)>180: text=text[:180]+"……"
            if kind == "recipes": text = f"{r.get('actionid','（自动／后续）')} · {text}"
            if kind == "elements": text = self.aspects(mod,r.get("aspects",{})) + " · " + text
            if kind == "endings": text = r.get("flavour","") + " · " + text
            lines.append(f"|-\n| {self.ref(mod,rid,kind=kind)} || <code>{safe(rid)}</code> || {safe(text)}")
        lines.append("|}")
        return "\n".join(lines)

    def references_for(self, mod, ids):
        """Return readable page links for all mod records that mention any ID."""
        ids = set(ids)
        records = self.mods[mod]["records"]
        out=[]
        for kind in ("recipes","decks"):
            for rid,rec in records[kind].items():
                if self.record_mentions(rec,ids):
                    out.append(self.ref(mod,rid,rec.get("label"),kind=kind))
        return list(dict.fromkeys(out))

    def record_mentions(self, value, ids, field=""):
        if isinstance(value,dict):
            return any(k in ids or self.record_mentions(v,ids,k) for k,v in value.items() if not k.startswith("_"))
        if isinstance(value,list):
            return any(self.record_mentions(v,ids,field) for v in value)
        return field in ("id","defaultcard","icon","image","filter","mutate") and value in ids

    def build_characters(self, mod):
        """Dedicated biographies and linked character task pages."""
        groups = {
            "contemnant": {
                "可招募人物": ["friend.eva","friend.vanja","friend.tibor","friend.walther"],
                "关键人物": ["contemnant.mentor","klei","friend.sergei","friend.cross","foe.marinette"]
            },
            "proterant": {
                "可招募人物": ["friend.fiorenza.local","friend.lorenzo.local","friend.padre.local","friend.daria.local"],
                "其他重要人物": ["friend.giorgiou","friend.orsolina","friend.wilhelm","friend.maccabee","friend.echidna","foe.orcul","foe.boccastrano"]
            },
            "obdurant": {
                "可招募人物": ["friend.yuri.local","friend.konstantin.local","friend.iosef.local","friend.nikolai.local"],
                "其他重要人物": ["friend.chaima","friend.zulfiya","foe.niniame","nimiane","obdurant.mentor"]
            }
        }
        added=[]
        for group,ids in groups[mod].items():
            for rid in ids:
                e=self.mods[mod]["records"]["elements"].get(rid)
                if not e: continue
                name=re.sub(r"<[^>]*>","",clean_text(e.get("label") or rid))
                if "#PREVIOUSCHARACTERNAME#" in name: name="前任流亡者"
                title=f"人物/{MODS[mod]['zh']}:{name}"
                if title in self.wiki.titles: title += f" ({rid})"
                icon=e.get("icon") or rid
                s=[f"{{{{Hatnote|所属 Mod：[[{MODS[mod]['zh']}]] · 卡牌与全部字段：{self.ref(mod,rid,'查看卡牌条目',kind='elements')}。}}}}",
                   '<table class="infobox character-profile"><tr><th colspan="2">'+safe(name)+'</th></tr>',
                   f'<tr><td colspan="2">{self.media_link(icon,180,name)}</td></tr>',
                   f'<tr><th>身份</th><td>{safe(group)}</td></tr>',
                   f'<tr><th>内部 ID</th><td><code>{safe(rid)}</code></td></tr></table>',
                   f'<div class="flavour">{rich_text(e["description"])}</div>']
                if e.get("aspects"):
                    s.append("== 能力 ==\n" + self.aspects(mod,e["aspects"]))
                base=rid.removesuffix(".local")
                ids_related={rid,base,base+".local",base+".wounded",base+".hidden",base+".exhausted",base+".damaged"}
                if rid.endswith(".mentor"):
                    ids_related.update({rid.replace(".mentor",".story"),"exile","duel.exile","exile.first","proterant.mentor","obdurant.mentor","contemnant.mentor"})
                if group=="可招募人物":
                    short=base.removeprefix("friend.")
                    ids_related.update({f"side.{short}",f"side.{short}.complete"})
                links=self.references_for(mod,ids_related)
                # Generic shared framework actions are only useful where the character
                # is specifically mentioned; all character-specific matches remain.
                if group=="可招募人物":
                    s.append("\n== 结识与招募 ==\n这些人物以当地盟友身份出现。与其交谈并满足个人委托的完成条件，可将其招募为能随队离开的友军；具体委托见下表。")
                    s.append("\n=== 个人委托 ===\n")
                    short=base.removeprefix("friend.")
                    for quest_id in (f"side.{short}",f"side.{short}.complete"):
                        quest=self.mods[mod]["records"]["elements"].get(quest_id)
                        if quest:
                            s.append(f"*{self.ref(mod,quest_id,quest.get('label'),kind='elements')}：{safe(quest.get('description',''))}")
                    s.append("\n=== 相关任务与事件 ===\n<details class=\"related-events\"><summary>展开相关行动（"+str(len(links))+"）</summary>\n"+"\n".join(f"* {l}" for l in links)+"\n</details>")
                    s.append("\n=== 成长与状态 ===\n* [[机制:盟友与招募|招募机制与经验升级]]\n* [[机制:伤口与治疗|负伤、枯竭与治疗]]\n* [[攻略:开局与资源|队伍配置建议]]")
                else:
                    s.append("\n== 相关事件 ==\n<details class=\"related-events\"><summary>展开相关行动（"+str(len(links))+"）</summary>\n"+"\n".join(f"* {l}" for l in links)+"\n</details>")
                others=[(m,r) for m in MODS for r in groups[m].get("可招募人物",[])+groups[m].get("其他重要人物",[])+groups[m].get("关键人物",[]) if r in self.mods[m]["records"]["elements"] and re.sub(r"<[^>]*>","",clean_text(self.mods[m]["records"]["elements"][r].get("label") or ""))==name and m!=mod]
                shared_names={"食铁者","大陆之敌","战争制造者","杜弗尔","前任流亡者"}
                if name in shared_names:
                    s.append(f"\n== 跨 Mod 人物 ==\n[[人物:{name}|阅读 Gemini 撰写的跨 Mod 编者介绍]]，包含该人物在其他传承中的相关条目。")
                if others:
                    s.append("\n== 同名人物 ==\n"+"\n".join(f"* [[人物/{MODS[m]['zh']}:{safe(name)}|{MODS[m]['zh']}]]" for m,_ in others))
                s.append(f"\n== 来源 ==\n人物原文：<code>{safe(self.mods[mod]['sources']['elements'][rid])}</code>。事件关系由本地 Mod 数据中的 ID 引用自动汇总；详细条件进入行动条目查看。\n\n[[分类:人物]][[分类:{MODS[mod]['zh']}·人物]][[分类:{MODS[mod]['zh']}·{group}]]")
                self.wiki.add(title,"\n".join(s))
                added.append((title,group))
        lines=[f"[[{MODS[mod]['zh']}|← {MODS[mod]['zh']}]]",f"这里按人物而非卡牌状态组织内容。共 {len(added)} 个人物专页；普通单位请见[[{MODS[mod]['zh']}/人物与盟友|盟友索引]]。",
               "跨 Mod 人物：[[人物:食铁者|食铁者]] · [[人物:大陆之敌|大陆之敌]] · [[人物:战争制造者|战争制造者]] · [[人物:杜弗尔|杜弗尔]] · [[人物:前任流亡者|前任流亡者]]；另见[[概念:长生者|长生者]]。",'<div class="profile-grid">']
        for title,group in added:
            lines.append(f'<div class="profile-tile"><strong>[[{title}|{safe(title.split(":",1)[1])}]]</strong><br/><small>{safe(group)}</small></div>')
        lines.append('</div>')
        self.wiki.add(f"{MODS[mod]['zh']}/人物","\n".join(lines))

    def build_routes(self, mod):
        routes=[]
        for r in self.mods[mod]["records"]["recipes"].values():
            rid=r.get("id","")
            if not rid.startswith("newwarzone."): continue
            deck=r.get("internaldeck",{})
            spec=deck.get("spec",[]) if isinstance(deck,dict) else []
            if not spec: continue
            # Route name and location IDs are more stable than display labels.
            parts=rid.split(".")
            if len(parts)<2: continue
            origin=parts[1]
            routes.append((origin,r,spec))
        if not routes: return
        nodes=sorted(set([o for o,_,_ in routes]+[c for _,_,spec in routes for c in spec]))
        s=[f"[[{MODS[mod]['zh']}|← {MODS[mod]['zh']}]] · [[机制:旅行与侦察|旅行机制说明]]",
           '<div class="route-intro">箭头表示从当前战区出发时，其路线牌组中可能出现的目的地，<strong>不代表固定传送点</strong>。行军期间可能进入远方战区；点击节点查看该地点的全部机制数据。</div>',
           '<div class="route-map">']
        for origin,r,spec in routes:
            origin_rec=self.mods[mod]["records"]["elements"].get(origin,{})
            name=origin_rec.get("label") or origin
            name=self.ref(mod,origin,name).replace(f'{MODS[mod]["zh"]}:','')
            s.append(f'<div class="route-origin"><h3>{name}</h3><div class="route-arrows">')
            for dest in dict.fromkeys(spec):
                drec=self.mods[mod]["records"]["elements"].get(dest,{})
                destination=self.ref(mod,dest,drec.get("label") or dest).replace(f'{MODS[mod]["zh"]}:','')
                s.append(f'<span class="route-destination">{destination}<small>可抽取目的地</small></span>')
            s.append(f'</div><p class="route-source">路线行动：{self.ref(mod,r["id"],r.get("label"),kind="recipes")}</p></div>')
        s.append('</div>')
        s.append("\n== 路线表 ==\n{| class=\"wikitable sortable route-table\"\n! 出发地 !! 可抽取目的地 !! 行军时间（秒） !! 路线行动")
        for origin,r,spec in routes:
            name=self.mods[mod]["records"]["elements"].get(origin,{}).get("label") or origin
            s.append(f"|-\n| {self.ref(mod,origin,name)} || "+"、".join(self.ref(mod,c) for c in dict.fromkeys(spec))+f" || {r.get('warmup','—')} || {self.ref(mod,r['id'],kind='recipes')}")
        s.append("|}\n\n== 读图提示 ==\n* 本图来自 <code>newwarzone.*</code> 行动的 <code>internaldeck</code>，不包含剧情强制移动或结局。\n* 同一目的地的多张牌只合并显示一次；各目的地的实际占比请查看对应牌组或路线行动。\n* [[攻略:开局与资源|行军前的补给与队伍准备]]。")
        self.wiki.add(f"{MODS[mod]['zh']}/战区路线图","\n".join(s))

    def guide_from_gemini(self, title, body):
        """Apply reviewed editorial corrections before publishing generated prose."""
        # Preserve the model's wording verbatim, including its editorial choices.
        return body.strip()
        return body.strip()

    def build_guides(self):
        for title in ("机制:战争基础","机制:盟友与招募","机制:伤口与治疗","机制:补给与行军","机制:密传与飞升","攻略:开局与资源","攻略:战斗准备"):
            path=ROOT/"data/generated"/(title+".wiki")
            if not path.exists(): continue
            body=path.read_text(encoding="utf-8").strip()
            footer="\n\n== 延伸阅读与数据 ==\n* [[攻略与机制|攻略与机制总入口]]"
            if title=="机制:战争基础":
                footer+="\n* [[坚毅使徒:敌军行动了！ (enemy.executeaction)|敌军行动数据]]\n* [[坚毅使徒:进行防御|防御行动数据]]\n* [[坚毅使徒/卡牌/敌人|敌人阈值索引]]"
            elif title=="机制:盟友与招募":
                footer+="\n* [[蔑世使徒/人物|蔑世人物]] · [[破军使徒/人物|破军人物]] · [[坚毅使徒/人物|坚毅人物]]\n* [[坚毅使徒:潜能显现|具名盟友升级行动]]"
            elif title=="机制:补给与行军":
                footer+="\n* [[蔑世使徒/战区路线图|蔑世路线]] · [[破军使徒/战区路线图|破军路线]] · [[坚毅使徒/战区路线图|坚毅路线]]"
            elif title=="攻略:战斗准备":
                footer+="\n* [[机制:战争基础|战争基础]] · [[机制:伤口与治疗|伤口与治疗]]"
            footer+="\n<div class=\"source-note\">正文由 Antigravity CLI 的 Gemini 3.8 Flash 依据本地 Mod 数据摘要撰写，保留原稿措辞。具体机制、阈值与行动条件以链接条目和原始 JSON 为准。</div>"
            self.wiki.add(title,body+footer)
        self.build_shared_characters()

    def build_shared_characters(self):
        people={
            "食铁者": {"icon":"sergei","mods":["obdurant","contemnant"],"ids":["sergei","friend.sergei"],"sources":["content/elements/long.json","content/elements/contemnant.json"]},
            "大陆之敌": {"icon":"camilla","mods":["obdurant","proterant"],"ids":["camilla","duel.camilla.proterant"],"sources":["content/elements/obdurant.json","content/elements/proterant.json"]},
            "战争制造者": {"icon":"wilhelm","mods":["obdurant","proterant"],"ids":["wilhelm","friend.wilhelm"],"sources":["content/elements/long.json","content/elements/proterant.json"]},
            "杜弗尔": {"icon":"duffoure","mods":["obdurant","contemnant"],"ids":["duel.foe","duffoure"],"sources":["content/elements/obdurant.json","content/elements/long_enemies.json"]},
            "前任流亡者": {"icon":"contemnant.mentor","mods":["obdurant","proterant","contemnant"],"ids":["obdurant.mentor","proterant.mentor","contemnant.mentor"],"sources":["content/elements/obdurant.json","content/elements/proterant.json","content/elements/contemnant.json"]},
        }
        for name,info in people.items():
            path=ROOT/"data/generated"/(name+".txt")
            if not path.exists(): continue
            s=[f'<div class="shared-character"><h2>{safe(name)}</h2><p>跨 Mod 人物 · 编者概述</p></div>',
               '<table class="infobox character-profile"><tr><th colspan="2">'+safe(name)+'</th></tr>',
               f'<tr><td colspan="2">{self.media_link(info["icon"],180,name)}</td></tr>',
               '<tr><th>常见身份</th><td>刃之长生者／与传承相关的关键人物</td></tr>',
               '<tr><th>涉及 Mod</th><td>'+"、".join(f'[[{MODS[m]["zh"]}]]' for m in info["mods"])+'</td></tr></table>',
               '<div class="editorial-profile">'+safe(path.read_text(encoding="utf-8")).replace("\n","<br/>")+'</div>',
               "\n== 各传承中的条目 ==\n"]
            for mod,rid in zip(info["mods"],info["ids"]):
                if self.title_for(mod,"elements",rid):
                    s.append(f"* {self.ref(mod,rid,MODS[mod]['zh']+'：'+name,kind='elements')}")
            s.append("\n== 来源与说明 ==\n本页简介由 Antigravity CLI 的 Gemini 3.8 Flash 根据以下本地 Mod 人物原文及相关决斗文本撰写，保留原稿；它是编者概述，不是 Mod 原文。不同传承中的出场不自动构成一条已证实的连续时间线。\n")
            for mod,src in zip(info["mods"],info["sources"]):
                s.append(f"* [[{MODS[mod]['zh']}]]：<code>{safe(src)}</code>")
            s.append("[[分类:人物]][[分类:跨Mod人物]]")
            self.wiki.add(f"人物:{name}","\n".join(s))
        self.wiki.add("概念:长生者","""'''长生者（Long）'''是《密教模拟器》世界中超越凡俗寿命的人物类别。在本 Wiki 的三个使徒 Mod 中，<code>edgelong</code> 表示刃之长生者；他们可能是主角的师友、敌人、决斗对手、见证者，也可能在特定剧情中成为盟友。

“长生者”不是“司辰”或“具名者”的同义词。人物在不同传承中的身份与经历应按各自条目阅读；同一人物跨 Mod 出场并不证明所有事件都处于同一条连续时间线。

== 本 Wiki 收录的跨 Mod 刃之长生者 ==
* [[人物:食铁者|食铁者]] · [[人物:大陆之敌|大陆之敌]] · [[人物:战争制造者|战争制造者]] · [[人物:杜弗尔|杜弗尔]] · [[人物:前任流亡者|前任流亡者]]

== 机制阅读 ==
人物页的正文为 Gemini 编者简介；人物身份、性相和事件条件仍以对应卡牌及行动页为准。长生者在战斗中的特殊应对不适用于所有人物，请查看具体配方。""")
        self.wiki.add("攻略与机制","""<div class="guide-hero"><h1>读懂战争</h1><p>从第一场侦察，到军团、伤口与最终飞升。</p></div>
<div class="guide-grid">
<div>[[机制:战争基础|'''战争基础''']]<br/>敌袭、阈值、并行行动与胜利判定。</div>
<div>[[机制:盟友与招募|'''盟友与招募''']]<br/>人物结识、委托、经验与单位职能。</div>
<div>[[机制:伤口与治疗|'''伤口与治疗''']]<br/>身体、精神、残疾、治疗及失败条件。</div>
<div>[[机制:补给与行军|'''补给与行军''']]<br/>补给、住宿、断粮与战区转移。</div>
<div>[[机制:密传与飞升|'''密传与飞升''']]<br/>刃密传成长、挑战、具名准备。</div>
<div>[[攻略:开局与资源|'''开局与资源攻略''']]<br/>如何组织一支能活下来的队伍。</div>
<div>[[攻略:战斗准备|'''战斗准备攻略''']]<br/>读懂敌人阈值，减少无效投入。</div>
</div>
'''说明：'''“机制”页依据本地数据明确写出可确认规则；“攻略”页是编者根据规则提出的建议。具体行动请通过页面中的链接查看原始条件。三个 Mod 共用部分机制，但并非所有条件都完全相同。""")
    def build_all(self):
        self.read_base()
        self.read_mods()
        self.allocate_titles()
        self.build_templates()
        for mod in MODS:
            self.build_mod(mod)
            self.build_characters(mod)
            self.build_routes(mod)
        self.build_aspects()
        self.build_guides()
        self.build_home()
        self.build_id_index()
        self.build_metadata()

    def build_templates(self):
        self.wiki.add("模板:未翻译", '<div class="notice">本条目的部分或全部文本暂无 Mod 自带简中翻译，保留原文。欢迎人工补充；机制数据与原文均已保留。</div>[[分类:待翻译条目]]')
        self.wiki.add("模板:消歧义提示", '<div class="notice">同名或同 ID 内容可能存在于其他 Mod。请留意页面所属的 Mod；同名条目链接见页底。</div>')
        self.wiki.add("模板:Hatnote", '<div class="hatnote">{{{1}}}</div>')
        self.wiki.add("模板:Documentation", '<noinclude><div class="notice">本地页面由数据导入器生成。修改条目会在下次全量导入时覆盖，请优先修改 tools/build_wiki.py 或对应 Mod 数据。</div></noinclude>')

    def build_mod(self,mod):
        m = self.mods[mod]
        for eid,e in m["records"]["elements"].items():
            self.wiki.add(self.title_for(mod,"elements",eid),self.element_page(mod,eid,e))
        for rid,r in m["records"]["recipes"].items():
            self.wiki.add(self.title_for(mod,"recipes",rid),self.recipe_page(mod,rid,r))
        for did,d in m["records"]["decks"].items():
            self.wiki.add(self.title_for(mod,"decks",did),self.deck_page(mod,did,d))
        for vid,v in m["records"]["verbs"].items():
            self.wiki.add(self.title_for(mod,"verbs",vid),self.verb_page(mod,vid,v))
        for eid,e in m["records"]["endings"].items():
            self.wiki.add(self.title_for(mod,"endings",eid),self.ending_page(mod,eid,e))
        for aid,a in m["records"]["achievements"].items():
            self.wiki.add(self.title_for(mod,"achievements",aid),self.achievement_page(mod,aid,a))
        for lid,l in m["records"]["legacies"].items():
            self.wiki.add(self.title_for(mod,"legacies",lid),self.legacy_page(mod,lid,l))
        for kind in KINDS:
            for rid,r in m["records"][kind].items():
                self.wiki.add(f"原始数据:{kind}/{mod}__{rid}",self.raw_page(mod,kind,rid,r,self.title_for(mod,kind,rid)))
        self.build_mod_index(mod)

    def build_mod_index(self,mod):
        m = self.mods[mod]; info = MODS[mod]; syn = m["synopsis"]
        s = [f'<div class="mod-hero mod-{mod}"><h1>{info["zh"]}</h1><p lang="en">{info["en"]}</p></div>',
             f'[[文件:{info["zh"]}_封面.png|缩略图|260px|{info["zh"]}封面]]',
             '<table class="infobox"><tr><th>作者</th><td>'+safe(syn.get("author",""))+'</td></tr>',
             '<tr><th>版本</th><td>'+safe(syn.get("version",""))+'</td></tr>',
             f'<tr><th>时间与地区</th><td>{info["year"]} 年 · {info["region"]}</td></tr>',
             '<tr><th>Steam 创意工坊</th><td>[https://steamcommunity.com/sharedfiles/filedetails/?id='+info["folder"]+' '+info["folder"]+']</td></tr></table>',
             f'<div class="flavour">{safe(syn.get("description",""))}<br/>{safe(syn.get("description_long",""))}</div>',
             "== 内容总览 ==",'{| class="wikitable sortable"\n! 类型 !! 条目数 !! 自带简中条目数']
        for kind in KINDS:
            recs = m["records"][kind]
            s.append(f"|-\n| [[{info['zh']}/{KIND_ZH[kind]}|{KIND_ZH[kind]}]] || {len(recs)} || {sum(bool(r.get('_has_zh')) for r in recs.values())}")
        s.append("|}\n\n== 编者概述 ==\n")
        overview_path = ROOT / "data" / f"{mod}-overview.txt"
        if overview_path.exists():
            s.append(f'<div class="flavour">{safe(overview_path.read_text(encoding="utf-8")).replace(chr(10),"<br/>")}</div>\n本段为编者概述，依据本 Mod 的传承与开局文本整理；具体事实以条目与原始数据为准。')
        s.append("\n== 阅读入口 ==\n<div class=\"mod-nav\">[[{0}/人物|人物专页]] · [[{0}/战区路线图|战区路线图]] · [[攻略与机制|机制与攻略]] · [[{0}/结局|结局]] · [[人物:食铁者|跨 Mod 人物]]</div>".format(info['zh']))
        s.append("\n== 数据导航 ==\n<div class=\"mod-nav\">" + " · ".join(f"[[{info['zh']}/{KIND_ZH[k]}|{KIND_ZH[k]}]]" for k in KINDS) + "</div>")
        s.append(f"\n== 数据源 ==\n* 本地目录：<code>D:/Steam/steamapps/workshop/content/718670/{info['folder']}/</code>\n* 共读取 {m['json_count']} 个 JSON 文件；所有内容数据以 ID 去重并保留原字段。")
        self.wiki.add(info["zh"],"\n".join(s))
        for kind in KINDS:
            title = f"{info['zh']}/{KIND_ZH[kind]}"
            txt = f"[[{info['zh']}|← 返回{info['zh']}]]\n\n本分类共 {len(m['records'][kind])} 个唯一条目。\n\n" + self.record_list(mod,kind,m["records"][kind].values())
            self.wiki.add(title,txt)
        # Content-class and narrative indexes supplement, never replace, the all-card index.
        index_groups = {
            "人物与盟友": ["盟友"], "敌人": ["敌人"], "战区与地点": ["战区","地点"],
            "密传与能力": ["密传","思考"], "剧情物品与遗骸": ["剧情物品","遗骸"],
            "伤口与阻碍": ["伤口与创伤","阻碍"], "武器与补给": ["武器","补给"]
        }
        for group,cats in index_groups.items():
            subset = [r for r in m["records"]["elements"].values() if any(c in self.card_categories(mod,r) for c in cats)]
            if subset:
                self.wiki.add(f"{info['zh']}/{group}",f"[[{info['zh']}|← {info['zh']}]]\n\n此索引包含 {len(subset)} 张卡牌，包括各状态变体与隐藏机制卡牌。\n\n"+self.record_list(mod,"elements",subset))
        # Every primary location gets a travel-routing summary based on internal decks.
        location_lines=[]
        for r in m["records"]["recipes"].values():
            deck=r.get("internaldeck",{})
            spec=deck.get("spec",[]) if isinstance(deck,dict) else []
            if r.get("id","").startswith("newwarzone.") and spec:
                location_lines.append(f"=== {safe(r.get('label') or r['id'])} ===\n入口行动：{self.ref(mod,r['id'],kind='recipes')}<br/>目的地：" + "、".join(self.ref(mod,c) for c in dict.fromkeys(spec)))
        if location_lines:
            self.wiki.add(f"{info['zh']}/战区路线",f"[[{info['zh']}|← {info['zh']}]]\n\n以下目的地由路线行动的内置牌组生成；重复目的地已合并，概率和抽牌规则请进入行动条目查看。\n\n"+"\n\n".join(location_lines))
        # Separate useful subindices, while all records remain in the main card index.
        for cat in ("盟友","敌人","战区","地点","武器","密传","补给","阻碍","伤口与创伤","剧情物品","其他卡牌"):
            subset = [r for r in m["records"]["elements"].values() if cat in self.card_categories(mod,r)]
            if subset:
                self.wiki.add(f"{info['zh']}/卡牌/{cat}",f"[[{info['zh']}/卡牌|← 全部卡牌]]\n\n共 {len(subset)} 个条目。\n\n"+self.record_list(mod,"elements",subset))

    def build_aspects(self):
        for aspect, owners in sorted(self.aspect_owners.items()):
            title = f"性相:{PRINCIPLES.get(aspect,aspect)}"
            if title in self.wiki.titles:
                title += f" ({aspect})"
            s = [f'<table class="infobox"><tr><th>内部 ID</th><td><code>{safe(aspect)}</code></td></tr>',
                 f'<tr><th>出现于</th><td>{len(owners)} 张 Mod 卡牌</td></tr></table>',
                 f'== 拥有此性相的卡牌 ==\n本页统计全部三个 Mod 的卡牌定义；{PRINCIPLES.get(aspect,"此性相")}的等级以各条目为准。',
                 '{| class="wikitable sortable"\n! 卡牌 !! Mod !! 等级']
            for mod,kind,rid in owners:
                rec = self.mods[mod]["records"][kind][rid]
                s.append(f"|-\n| {self.ref(mod,rid,kind=kind)} || [[{MODS[mod]['zh']}]] || {rec['aspects'][aspect]}")
            s.append("|}\n\n性相只表示卡牌具备某类属性或标签；它并不等同于同名实体卡牌。")
            s.append("[[分类:性相]]")
            self.wiki.add(title,"\n".join(s))

    def build_home(self):
        total = {k:sum(len(self.mods[m]["records"][k]) for m in MODS) for k in KINDS}
        s = ['<div class="main-title"><span class="eyebrow">CULTIST SIMULATOR · LOCAL MOD ARCHIVE</span><h1>三刃使徒 Wiki</h1><p>蔑世使徒 · 破军使徒 · 坚毅使徒</p></div>',
             '<div class="main-intro">二战的三条战线，三段相交的历史。这里收录 Sneakworks 的三个《密教模拟器》使徒 Mod 的本地数据、中文文本、行动链与美术资源。本 Wiki 包含完整剧情及机制剧透。</div>',
             '<div class="guide-grid home-guides"><div>[[机制:战争基础|<strong>战争基础</strong>]]<br/>敌袭、阈值与战斗判定</div><div>[[攻略:开局与资源|<strong>开局攻略</strong>]]<br/>队伍、补给与人物招募</div><div>[[机制:盟友与招募|<strong>盟友机制</strong>]]<br/>结识、委托、成长与治疗</div><div>[[攻略与机制|<strong>全部机制与攻略 →</strong>]]<br/>密传、飞升、行军与战斗准备</div></div>',
             '<div class="mod-grid">']
        for mod,info in MODS.items():
            s.append(f'<div class="mod-tile mod-{mod}">[[文件:{info["zh"]}_封面.png|260px|link={info["zh"]}]]<h2>[[{info["zh"]}]]</h2><p>{info["year"]} · {info["region"]}<br/><span lang="en">{info["en"]}</span></p><p>[[{info["zh"]}/人物|人物]] · [[{info["zh"]}/战区路线图|路线图]] · [[{info["zh"]}/卡牌|卡牌]] · [[{info["zh"]}/行动|行动]] · [[{info["zh"]}/结局|结局]]</p></div>')
        s.append('</div>\n== 资料索引 ==\n{| class="wikitable main-stats"\n! 类型 !! 条目数 !! 说明')
        descriptions = {"elements":"含隐藏机制卡牌；性相不是实体卡牌。","recipes":"行动条件、槽位、概率、产出与后续链。","decks":"抽牌构成、默认卡与重置规则。","verbs":"Mod 自定义行动槽；共用本体行动槽见行动页面。","legacies":"开局、背景与初始卡牌。","endings":"结局全文、触发行动、图像与音频。","achievements":"成就描述与解锁信息。"}
        for kind in KINDS:
            s.append(f"|-\n| {KIND_ZH[kind]} || {total[kind]} || {descriptions[kind]}")
        s.append('|}\n\n== 使用说明 ==\n* 搜索“中文名称”或“内部 ID”；同名卡牌会标明所属 Mod。\n* 每张卡牌与行动页底部都有“完整 JSON”，以保留全部机制字段。\n* 字段优先采用 Mod 自带简中；未翻译文本保留英文，不自行编造名称或数值。\n* [[性相:刃|性相索引]] · [[项目:ID索引|内部 ID 索引]] · [[项目:关于|关于本站]] · [[项目:维护报告|完整性报告]]\n\n本站是非官方的本地资料整理，不隶属于灰机 Wiki、Weather Factory 或 Mod 作者。')
        self.wiki.add("首页","\n".join(s))
        overview_path = ROOT / "data" / "overview.txt"
        if overview_path.exists():
            overview = overview_path.read_text(encoding="utf-8").strip()
            self.wiki.add("三刃使徒",f"== 编者概述 ==\n<div class=\"flavour\">{safe(overview).replace(chr(10),'<br/>')}</div>\n本节由 Antigravity CLI 的 Gemini 3.8 Flash 根据 Mod 简介概括，并标注为编者概述；原文与数据以三个 Mod 的条目为准。\n\n== 三个传承 ==\n" + "\n".join(f"* [[{info['zh']}|{info['zh']}（{info['en']}）]]：{info['year']} 年，{info['region']}。" for info in MODS.values()))

    def build_id_index(self):
        lines = ["本页列出所有 Mod 条目的内部 ID。可直接复制 ID 到搜索框查找。",
                 '{| class="wikitable sortable"\n! 内部 ID !! 类型 !! 条目']
        for (mod,kind,rid),title in self.titles.items():
            lines.append(f"|-\n| <code>{safe(rid)}</code> || {MODS[mod]['zh']}·{KIND_ZH[kind]} || [[{title}]]")
        lines.append("|}")
        self.wiki.add("项目:ID索引","\n".join(lines))

    def build_metadata(self):
        self.wiki.add("项目:关于","""== 范围 ==
收录蔑世使徒、破军使徒、坚毅使徒，分别对应 Apostle Contemnant、Apostle Proterant、Apostle Obdurant。

== 数据原则 ==
* 所有机制数据直接来自本地 Steam 创意工坊 Mod 文件。
* 中文来自 Mod 自带 loc_zh-hans；没有中文时显示英文。
* 可读条目与完整 JSON 一一对应；源文件路径保留于各条目页底。
* 中文本地化中出现的机制字段覆盖不会被静默采用，详见维护报告。
* “行动”是数据中的 recipe，包含玩家可启动行动、自动行动与后续分支。

== 版权 ==
《密教模拟器》及 Mod 的文字与美术版权归各自权利人。本站仅作为本机私人的游戏资料索引，不上传至公共网站。灰机 Wiki 仅作为页面架构参考，没有复制其正文。""")
        lines = ["== 导入统计 ==",'{| class="wikitable"\n! Mod !! 文件数 !! ' + ' !! '.join(KIND_ZH[k] for k in KINDS)]
        for mod in MODS:
            m = self.mods[mod]
            lines.append(f"|-\n| [[{MODS[mod]['zh']}]] || {m['json_count']} || " + " || ".join(str(len(m['records'][k])) for k in KINDS))
        lines.append("|}\n\n== 数据检查 ==")
        if self.reports:
            for key,val in sorted(self.reports.items()): lines.append(f"* <code>{safe(key)}</code>：{val}")
        else:
            lines.append("* 未发现重复 ID、缺失 ID 或本地化机制字段覆盖。")
        lines.append("* 所有 JSON 均已成功解析。Mod 文件省略的对象／数组成员逗号仅作语法恢复；数值、字符串及数组重复项均保留。")
        lines.append("* 来源图片与音频只依据本地文件名去重；Mod 对本体资源的引用保留为文字说明。")
        lines.append("\n== 简中本地化与机制数据差异 ==\n以下为本地化文件与对应内容数据不同的非文本字段。页面采用内容数据的原始值；差异原样列出，不推断哪个版本是作者本意。完整差异也保存在 build/locale-overrides.json。")
        if self.locale_overrides:
            lines.append('{| class="wikitable sortable"\n! Mod !! 条目 ID !! 字段 !! 内容数据 !! 简中本地化')
            for d in self.locale_overrides:
                lines.append(f"|-\n| [[{MODS[d['mod']]['zh']}]] || {self.ref(d['mod'],d['id'],kind=d['kind'])} || <code>{safe(d['field'])}</code> || <code>{safe(self.pretty(d['content']))}</code> || <code>{safe(self.pretty(d['localization']))}</code>")
            lines.append("|}")
        else:
            lines.append("没有非文本字段差异。")
        lines.append("\n== 重建 ==\n运行 <code>python -I tools/build_wiki.py</code>，再运行 <code>powershell -ExecutionPolicy Bypass -File tools/import-wiki.ps1</code>。")
        self.wiki.add("项目:维护报告","\n".join(lines))
        self.wiki.add("MediaWiki:Mainpage","首页")
        self.wiki.add("MediaWiki:Sidebar","""* 导航
** 首页|首页
** 蔑世使徒|蔑世使徒
** 破军使徒|破军使徒
** 坚毅使徒|坚毅使徒
** 攻略与机制|机制与攻略
** 攻略:开局与资源|开局攻略
* 快速索引
** 蔑世使徒/卡牌|蔑世·卡牌
** 破军使徒/卡牌|破军·卡牌
** 坚毅使徒/卡牌|坚毅·卡牌
** 特殊:所有页面|全部页面
** 特殊:分类|分类
** 项目:维护报告|维护报告
* 工具
** 特殊:最近更改|最近更改
** 特殊:上传文件|上传文件""")
        self.wiki.add("MediaWiki:Common.css",COMMON_CSS)
        self.wiki.add("MediaWiki:Vector.css",COMMON_CSS)
        self.wiki.add("MediaWiki:Vector-2022.css",COMMON_CSS)
        self.wiki.add("MediaWiki:Timeless.css",COMMON_CSS)


COMMON_CSS = r'''
/* Readable light archive theme. Source art remains the visual accent. */
:root { --ink:#252a33; --paper:#f6f4ef; --panel:#ffffff; --gold:#805c2b; --line:#d5d8de; --muted:#596474; --blue:#175ca3; --heading:#1b2d43; }
html, body { background:#eeefec; color:var(--ink); }
.mw-page-container { max-width:none; }
.mw-content-container, .mw-body, .mw-body-content { max-width:none; }
.vector-feature-limited-width-content .mw-body { max-width:1600px; }
@media (min-width:1200px) { .mw-page-container { margin:0 48px; } .mw-content-container { max-width:none; } .vector-feature-limited-width-content .mw-body { max-width:1500px; } }
.mw-body, .mw-body-content, .mw-parser-output, .mw-content-ltr, .mw-content-rtl { color:var(--ink); font-size:17px; line-height:1.85; }
.mw-body { background:var(--panel); border:1px solid #e0e2e6; padding:28px 34px; box-shadow:0 2px 12px #2332470a; }
.mw-body h1, .mw-body h2, .mw-body h3, .mw-body h4 { color:var(--heading); font-family:"Microsoft YaHei",sans-serif; border-color:var(--line); line-height:1.45; }
.mw-body h2 { font-size:1.5em; margin-top:1.4em; } .mw-body h3 { font-size:1.2em; }
a { color:var(--blue); text-decoration:none; } a:hover, a:focus { text-decoration:underline; } a:visited { color:#315b86; } a.new { color:#b1362d; }
code, pre { background:#f0f2f5; color:#24364c; border:1px solid #d3dae4; }
code { padding:1px 4px; overflow-wrap:anywhere; } pre { padding:12px; white-space:pre-wrap; overflow-wrap:anywhere; line-height:1.6; }
.infobox { float:right; clear:right; margin:0 0 20px 24px; width:310px; max-width:45%; border-collapse:collapse; background:var(--panel); border:1px solid #c8cdd5; box-shadow:0 3px 10px #1d2b3b0a; }
.infobox th, .infobox td { padding:9px 10px; border:1px solid var(--line); text-align:left; vertical-align:top; overflow-wrap:anywhere; }
.infobox tr:first-child th { text-align:center; background:#e7ecf2; color:#213a58; font-size:1.12em; }
.character-profile { min-width:290px; }
.character-profile .mw-file-description, .character-profile .thumb { display:block; margin:0 auto; }
.infobox td[colspan] { text-align:center; background:#f2f3f4; } .infobox img { max-width:100%; height:auto; }
.card-image img { background:#e4e5e6; padding:8px; } .card-art { border:0; }
.wikitable { background:var(--panel); border:1px solid #c5cbd3; border-collapse:collapse; margin:10px 0 18px; }
.wikitable th { background:#e5eaf0; color:#233a54; } .wikitable th, .wikitable td { border:1px solid var(--line); padding:9px; }
.wikitable tr:nth-child(even) td { background:#fafbfb; } .wikitable td { vertical-align:top; }
.sanren-data > tbody > tr > th { width:180px; } .sanren-data .wikitable { font-size:.94em; }
.compact { width:auto; min-width:240px; margin:5px 0; } .compact th, .compact td { padding:5px 8px; }
.sanren-index td:last-child { min-width:320px; } .sanren-index td:first-child { font-weight:600; }
.flavour { background:#f7f3eb; color:#3d362b; border:1px solid #e7dfd1; border-left:4px solid #9d7a45; padding:15px 19px; margin:14px 0; line-height:1.95; }
.quote { font-style:italic; } .notice { border:1px solid #d6c39d; background:#fff8e8; color:#564628; padding:10px 14px; margin:10px 0; }
.hatnote { color:var(--muted); font-size:.94em; } .missing-art { color:#646b74; }
.main-title { border-top:3px solid #526c88; border-bottom:1px solid var(--line); padding:25px 0 22px; background:#f6f8fb; }
.main-title h1 { font-family:serif; font-size:2.7em; font-weight:500; letter-spacing:.08em; color:#20354e; border:0; margin:.15em 0; }
.main-title p { letter-spacing:.2em; color:#526c88; } .eyebrow { color:var(--muted); font-size:.75em; letter-spacing:.1em; }
.main-intro { padding:20px 0; max-width:900px; line-height:1.9; }
.mod-grid { display:flex; gap:18px; flex-wrap:wrap; margin:20px 0; } .mod-tile { flex:1; min-width:200px; border:1px solid #d4d8df; border-top:3px solid #6c8198; background:var(--panel); padding:0 14px 14px; }
.mod-tile h2 { border:0; font-size:1.35em; } .mod-tile img { width:100%; height:auto; } .mod-contemnant { border-top-color:#716b64; } .mod-proterant { border-top-color:#a26145; } .mod-obdurant { border-top-color:#547a92; }
.mod-hero { padding:10px 0; } .mod-hero h1 { border:0; margin:0; } .mod-hero p { color:var(--muted); }
.mod-nav { padding:12px 15px; border:1px solid var(--line); background:#f4f6f9; margin:10px 0; line-height:2; }
.guide-hero { background:#eaf0f6; padding:22px; border-left:4px solid #526c88; margin-bottom:20px; } .guide-hero h1 { border:0; margin:0; }
.guide-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:12px; margin:20px 0; }
.guide-grid > div { background:#f7f9fc; border:1px solid #d4dde7; padding:16px; border-top:3px solid #7892af; line-height:1.75; }
.guide-grid a { font-size:1.05em; } .home-guides { margin-bottom:25px; }
.profile-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px; }
.profile-tile { border:1px solid #d6dce4; background:#f8fafc; padding:15px; } .profile-tile small { display:block; margin-top:4px; }
.route-intro { padding:14px 16px; background:#eef4f8; border:1px solid #d2dfe8; margin-bottom:18px; }
.route-map { display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:16px; }
.route-origin { border:1px solid #cbd4dd; background:#fbfcfd; padding:14px 16px; }
.route-origin h3 { margin:0 0 12px; border:0; } .route-arrows { display:flex; flex-wrap:wrap; gap:8px; }
.route-destination { background:#e9f0f8; border:1px solid #c5d6e7; border-radius:3px; padding:7px 9px; }
.route-destination:before { content:'→ '; color:#537796; } .route-destination small { display:block; font-size:.72em; color:#5d6b78; }
.route-source { font-size:.85em; border-top:1px solid #dce2e8; padding-top:9px; margin-bottom:0; }
.related-events { border:1px solid var(--line); background:#fafbfc; padding:10px 14px; margin:10px 0; }
.related-events summary { cursor:pointer; color:#294d71; font-weight:600; }
.related-events ul { padding-left:22px; }
.editorial-profile { max-width:850px; font-size:1.06em; line-height:1.95; }
.shared-character { border-left:4px solid #9d7a45; padding:4px 16px; background:#f7f3eb; margin:12px 0 20px; }
.shared-character h2 { border:0; margin:0; } .shared-character p { margin:4px 0; color:#596474; }
.source-note { border-top:1px solid var(--line); margin-top:18px; padding-top:12px; color:#596474; font-size:.9em; }
.ending-text { max-width:900px; } small { color:var(--muted); }
.mw-category, .catlinks { color:#3d4652; } .mw-category a { color:var(--blue); }
#siteNotice, #localNotice, .mw-indicators, .mw-editsection, .mw-jump-link { color:#4e5a6b; }
#mw-header, #mw-page-base, .vector-header-container, .vector-sticky-pinned-container { background:#fff; }
.vector-menu-content, .vector-dropdown-content, .mw-portlet-body { background:#fff; color:var(--ink); }
@media (max-width:850px) { .mw-body { padding:18px; } .infobox { float:none; width:100%; max-width:100%; margin:0 0 18px; } .mod-grid { display:block; } .mod-tile { margin-bottom:15px; } .main-title h1 { font-size:2em; } .sanren-index { display:block; overflow:auto; } .route-map { grid-template-columns:1fr; } }
'''


def main():
    global WORKSHOP, GAME
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workshop", type=Path, default=WORKSHOP)
    parser.add_argument("--game", type=Path, default=GAME)
    args = parser.parse_args()
    WORKSHOP, GAME = args.workshop, args.game
    b = Builder()
    b.build_all()
    out = ROOT / "build"
    out.mkdir(exist_ok=True)
    b.wiki.export(out / "sanren-pages.xml")
    manifest = {"pages": len(b.wiki.pages), "statistics": dict(b.wiki.stats),
                "mods": {mod:{kind:len(b.mods[mod]["records"][kind]) for kind in KINDS} for mod in MODS},
                "titles": {f"{m}|{k}|{rid}":title for (m,k,rid),title in b.titles.items()},
                "warnings":dict(b.reports)}
    write_text(out / "manifest.json",json.dumps(manifest,ensure_ascii=False,indent=2))
    # Report every record and its source hash for repeatability, without copying the mods.
    audit=[]
    for mod in MODS:
        for kind in KINDS:
            for rid,rec in b.mods[mod]["records"][kind].items():
                audit.append({"mod":mod,"kind":kind,"id":rid,"title":b.title_for(mod,kind,rid),
                              "source":b.mods[mod]["sources"][kind][rid],"zh":bool(rec.get("_has_zh"))})
    write_text(out / "records.json",json.dumps(audit,ensure_ascii=False,indent=2))
    # Per-page text files are imported with edit.php instead of XML. This avoids
    # MediaWiki's importer recursively parsing escaped HTML in game prose.
    page_dir = out / "pages"
    if page_dir.exists():
        for old in page_dir.glob("*.wiki"):
            old.unlink()
    page_manifest=[]
    for index, page in enumerate(b.wiki.pages):
        filename=f"{index:05d}__{safe_filename(page['title'])}.wiki"
        write_text(page_dir / filename,page["text"])
        page_manifest.append({"file":filename,"title":page["title"],"comment":page["comment"]})
    write_text(out / "pages.json",json.dumps(page_manifest,ensure_ascii=False,indent=2))
    write_text(out / "locale-overrides.json",json.dumps(b.locale_overrides,ensure_ascii=False,indent=2))
    # Use each mod's own unlocalized ID for its card icon when possible.
    images = {}
    for mod in MODS:
        root = b.mods[mod]["root"]
        for img in (root / "images").rglob("*.png"):
            images.setdefault(img.stem.lower(), img)
    covers = {MODS[mod]["zh"] + "_封面.png": b.mods[mod]["root"] / "cover.png" for mod in MODS}
    missing = []
    for title,text in [(p["title"],p["text"]) for p in b.wiki.pages]:
        for match in re.finditer(r'\[\[文件:Mod/([^\]|]+)', text):
            name = match.group(1)
            if name.lower().endswith(".png") and name[:-4].lower() not in images:
                missing.append({"page":title,"image":name})
    image_manifest = {"files": {f"Mod/{safe_filename(img.name)}":str(img) for img in images.values()},
                      "covers": {name:str(path) for name,path in covers.items()},
                      "missing_image_references": missing}
    write_text(out / "media.json",json.dumps(image_manifest,ensure_ascii=False,indent=2))
    print(json.dumps(manifest["mods"],ensure_ascii=False,indent=2))
    print(f"Generated {len(b.wiki.pages)} pages: {out / 'sanren-pages.xml'}")
    print(f"Warnings: {sum(b.reports.values())}")


if __name__ == "__main__":
    main()
