#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
国語科 学会・研究会カレンダー — サイト生成スクリプト

events.json (Notionデータベースからエクスポートした全件) を読み込み、
- 開催日(または終了日)が本日以降のものだけを抽出
- 学会・団体ごとにカテゴリ分け
- 開催日の早い順にソート
して index.html を再生成する。

このスクリプトは「学会・研究会情報 週次収集」ルーティン実行時に
Claudeが毎回呼び出す想定(Notionへの新規追加後に events.json を更新し、
本スクリプトで index.html を再生成 → git commit & push)。
"""
import json
import re
import datetime
import html
import sys
from pathlib import Path

ROOT = Path(__file__).parent
EVENTS_PATH = ROOT / "events.json"
OUTPUT_PATH = ROOT / "index.html"

# カテゴリ判定ルール(先にマッチしたものを採用)。イベント名に含まれるキーワードで判定する。
CATEGORY_RULES = [
    ("早稲田大学国語教育学会", ["早稲田大学国語教育学会"]),
    ("全国大学国語教育学会", ["全国大学国語教育学会"]),
    ("日本国語教育学会", ["日本国語教育学会"]),
    ("国語教育史学会", ["国語教育史学会"]),
    ("教科教育史研究会", ["教科教育史研究会"]),
    ("古典教材開発研究センター(コテキリの会)", ["コテキリ", "古典教材開発研究センター"]),
    ("全国漢文教育学会", ["全国漢文教育学会"]),
    ("大村はま記念国語教育の会", ["大村はま"]),
    ("教育関連学会連絡協議会", ["教育関連学会連絡協議会"]),
    ("国語教育史と実践に学ぶ会", ["国語教育史と実践に学ぶ会"]),
    ("國學院大學国語教育研究会", ["國學院大學", "国学院大学"]),
    ("日本文学協会", ["日本文学協会"]),
    ("國文學會", ["國文學會", "国文学会"]),
]
OTHER_CATEGORY = "その他の勉強会・研究会"

DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def categorize(name: str) -> str:
    for category, keywords in CATEGORY_RULES:
        if any(kw in name for kw in keywords):
            return category
    return OTHER_CATEGORY


def parse_dates(event_date: str):
    """EventDateの文字列から (開始日, 終了日) の date オブジェクトを返す。終了日がなければ開始日と同じ。"""
    matches = DATE_RE.findall(event_date or "")
    if not matches:
        return None, None
    dates = [datetime.date(int(y), int(m), int(d)) for y, m, d in matches]
    start = dates[0]
    end = dates[-1]
    return start, end


def load_events():
    with open(EVENTS_PATH, encoding="utf-8") as f:
        return json.load(f)


def build(today: datetime.date):
    events = load_events()
    upcoming = []
    for ev in events:
        start, end = parse_dates(ev.get("eventDate", ""))
        if end is None:
            # 日付が読み取れないものは末尾に回さず一覧からは除外(要目視確認)
            continue
        if end < today:
            continue
        ev = dict(ev)
        ev["_start"] = start
        ev["_end"] = end
        ev["_category"] = categorize(ev["name"])
        upcoming.append(ev)

    upcoming.sort(key=lambda e: e["_start"])

    groups = {}
    for ev in upcoming:
        groups.setdefault(ev["_category"], []).append(ev)

    # カテゴリの表示順は CATEGORY_RULES の順、最後にその他
    ordered_categories = [c for c, _ in CATEGORY_RULES if c in groups]
    if OTHER_CATEGORY in groups:
        ordered_categories.append(OTHER_CATEGORY)

    return ordered_categories, groups, len(upcoming)


def fmt_date(d: datetime.date, end: datetime.date) -> str:
    wd = "月火水木金土日"[d.weekday()]
    if end and end != d:
        wd2 = "月火水木金土日"[end.weekday()]
        if d.month == end.month:
            return f"{d.year}/{d.month}/{d.day}({wd})〜{end.day}({wd2})"
        return f"{d.year}/{d.month}/{d.day}({wd})〜{end.month}/{end.day}({wd2})"
    return f"{d.year}/{d.month}/{d.day}({wd})"


def render_source(source: str) -> str:
    source = source or ""
    if source.startswith("http"):
        return f'<a href="{html.escape(source)}">{html.escape(source)}</a>'
    return html.escape(source)


def render_card(ev) -> str:
    when = fmt_date(ev["_start"], ev["_end"])
    deadline = ev.get("deadline")
    deadline_html = (
        f'<p class="deadline">締切 {html.escape(deadline)}</p>' if deadline else ""
    )
    return f"""
    <article class="card">
      <p class="card-when">{html.escape(when)}</p>
      <h3 class="card-title">{html.escape(ev['name'])}</h3>
      {deadline_html}
      <p class="card-src">情報源: {render_source(ev.get('source', ''))}</p>
    </article>"""


def render_category(name: str, evs) -> str:
    cards = "\n".join(render_card(e) for e in evs)
    return f"""
    <section class="category">
      <h2 class="category-title">{html.escape(name)}<span class="count">{len(evs)}件</span></h2>
      <div class="card-grid">{cards}
      </div>
    </section>"""


TEMPLATE = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>国語科 学会・研究会カレンダー</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Shippori+Mincho+B1:wght@500;700&family=Noto+Sans+JP:wght@400;500;600;700&display=swap');
  :root{{
    --ink:#262220; --paper:#F2EFE7; --paper-raised:#FBF9F3;
    --indigo:#2F4C6B; --indigo-soft:#EDF1F4; --gold:#A8752F;
    --rule:#D8D2C2; --muted:#6B6558;
    --shadow: 0 1px 2px rgba(38,34,32,.06), 0 6px 20px rgba(38,34,32,.05);
    color-scheme: light dark;
  }}
  @media (prefers-color-scheme: dark){{
    :root{{
      --ink:#EDE7DC; --paper:#1C1A17; --paper-raised:#26231F;
      --indigo:#8FB3D6; --indigo-soft:#232B32; --gold:#D6A45C;
      --rule:#3A352C; --muted:#A79E8C;
      --shadow: 0 1px 2px rgba(0,0,0,.3), 0 8px 24px rgba(0,0,0,.35);
    }}
  }}
  *{{box-sizing:border-box;}}
  body{{margin:0;background:var(--paper);color:var(--ink);
    font-family:'Noto Sans JP','Hiragino Sans',sans-serif;line-height:1.7;
    padding:40px 20px 64px;}}
  .wrap{{max-width:920px;margin:0 auto;}}
  header{{border-bottom:2px solid var(--ink);padding-bottom:18px;margin-bottom:8px;
    display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap;}}
  h1{{font-family:'Shippori Mincho B1',serif;font-weight:700;
    font-size:clamp(24px,4.5vw,32px);margin:0;text-wrap:balance;}}
  .updated{{font-size:12.5px;color:var(--muted);font-variant-numeric:tabular-nums;white-space:nowrap;}}
  .lede{{font-size:13.5px;color:var(--muted);margin:14px 0 36px;}}
  .category{{margin-bottom:38px;}}
  .category-title{{font-family:'Shippori Mincho B1',serif;font-size:19px;font-weight:700;
    display:flex;align-items:baseline;gap:10px;margin:0 0 14px;
    border-bottom:1px solid var(--rule);padding-bottom:8px;}}
  .category-title .count{{font-family:'Noto Sans JP',sans-serif;font-size:11.5px;font-weight:500;
    color:var(--muted);background:var(--indigo-soft);padding:2px 8px;border-radius:10px;}}
  .card-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px;}}
  .card{{background:var(--paper-raised);border:1px solid var(--rule);border-radius:6px;
    box-shadow:var(--shadow);padding:16px 18px;}}
  .card-when{{font-size:12.5px;color:var(--indigo);font-weight:600;
    font-variant-numeric:tabular-nums;margin:0 0 6px;}}
  .card-title{{font-family:'Shippori Mincho B1',serif;font-size:16px;font-weight:700;
    margin:0 0 8px;text-wrap:balance;}}
  .deadline{{font-size:12px;color:var(--gold);margin:0 0 6px;}}
  .card-src{{font-size:11.5px;color:var(--muted);margin:8px 0 0;
    word-break:break-all;}}
  .card-src a{{color:var(--muted);}}
  footer{{border-top:1px solid var(--rule);padding-top:18px;margin-top:20px;
    font-size:12px;color:var(--muted);}}
  footer a{{color:var(--indigo);}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>国語科 学会・研究会カレンダー</h1>
    <p class="updated">最終更新 {updated}</p>
  </header>
  <p class="lede">高校国語科向けに、学会公式サイトおよびメール案内から収集した今後開催予定のイベント一覧です(全{total}件)。Notionデータベースで重複チェックのうえ自動更新しています。</p>
  {sections}
  <footer>
    このページは「学会・研究会情報 収集ルーティン」が巡回のたびに自動更新しています。掲載内容の正確性は各学会の公式サイトでご確認ください。
  </footer>
</div>
</body>
</html>
"""


def main():
    today = datetime.date.today()
    if len(sys.argv) > 1:
        today = datetime.date.fromisoformat(sys.argv[1])
    ordered_categories, groups, total = build(today)
    sections = "\n".join(render_category(c, groups[c]) for c in ordered_categories)
    output = TEMPLATE.format(
        updated=today.isoformat(),
        total=total,
        sections=sections,
    )
    OUTPUT_PATH.write_text(output, encoding="utf-8")
    print(f"Wrote {OUTPUT_PATH} ({total} upcoming events, {len(ordered_categories)} categories)")


if __name__ == "__main__":
    main()
