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
import hashlib
import json
import re
import urllib.parse
import datetime
import html
import sys
from pathlib import Path

ROOT = Path(__file__).parent
EVENTS_PATH = ROOT / "events.json"
OUTPUT_PATH = ROOT / "index.html"
ICS_PATH = ROOT / "calendar.ics"
ICS_DIR = ROOT / "ics"
SITE_URL = "https://upopotennis-gif.github.io/kokugo-kenkyukai-info/"

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
    ("國學院大學國文學會", ["國學院大學國文學會", "國文學會", "国文学会"]),
    ("國學院大學国語教育研究会", ["國學院大學", "国学院大学"]),
    ("日本文学協会", ["日本文学協会"]),
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
        events = json.load(f)
    # hidden.json: サイトに出さないイベント名の一覧(Notionには残す)
    hidden_path = ROOT / "hidden.json"
    hidden = set(json.load(open(hidden_path, encoding="utf-8"))) if hidden_path.exists() else set()
    return [e for e in events if e.get("name") not in hidden]


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

    # カテゴリは「そのカテゴリの最初の(いちばん近い)予定」の開催日・時間が早い順に並べる。
    # 同じ日どうしは時間(開始時刻)、それも同じなら CATEGORY_RULES の順。
    rule_index = {c: i for i, (c, _) in enumerate(CATEGORY_RULES)}

    def first_key(cat):
        first = min(groups[cat], key=lambda e: (e["_start"], e["_end"], e.get("time") or ""))
        return (first["_start"], first.get("time") or "", rule_index.get(cat, len(rule_index)))

    ordered_categories = sorted(groups, key=first_key)

    return ordered_categories, groups, len(upcoming)


def fmt_date(d: datetime.date, end: datetime.date) -> str:
    wd = "月火水木金土日"[d.weekday()]
    if end and end != d:
        wd2 = "月火水木金土日"[end.weekday()]
        if d.month == end.month:
            return f"{d.year}/{d.month}/{d.day}({wd})〜{end.day}({wd2})"
        return f"{d.year}/{d.month}/{d.day}({wd})〜{end.month}/{end.day}({wd2})"
    return f"{d.year}/{d.month}/{d.day}({wd})"


URL_OR_MAIL = re.compile(r"(https?://[^\s<>\"]+|[\w.+-]+@[\w-]+(?:\.[\w-]+)+)")


def source_url(source: str) -> str:
    """情報源がURLならそのURL(空白以降の注記は捨てる)、メール等なら空文字。"""
    source = (source or "").strip()
    if source.startswith("http"):
        return source.split()[0]
    return ""


def autolink(text: str) -> str:
    """文中のURLとメールアドレスをリンクにする。"""
    out, pos = [], 0
    for m in URL_OR_MAIL.finditer(text):
        out.append(html.escape(text[pos:m.start()]))
        tok = m.group(0)
        href = tok if tok.startswith("http") else "mailto:" + tok
        out.append(f'<a href="{html.escape(href)}">{html.escape(tok)}</a>')
        pos = m.end()
    out.append(html.escape(text[pos:]))
    return "".join(out)


def render_card(ev) -> str:
    when = fmt_date(ev["_start"], ev["_end"])
    if (ev.get("time") or "").strip():
        when += " " + ev["time"].strip()
    deadline = ev.get("deadline")
    deadline_html = (
        f'<p class="deadline">締切 {html.escape(deadline)}</p>' if deadline else ""
    )
    url = source_url(ev.get("source", ""))
    src_html = (
        f'<p class="card-src">情報源: <a href="{html.escape(url)}">{html.escape(url)}</a></p>'
        if url else ""
    )
    apply = (ev.get("apply") or "").strip()
    apply_html = f'<p class="apply">申込方法 {autolink(apply)}</p>' if apply else ""
    return f"""
    <article class="card" id="{ev['_id']}">
      <p class="card-when">{html.escape(when)}</p>
      <h3 class="card-title">{html.escape(ev['name'])}</h3>
      {deadline_html}
      {apply_html}
      {src_html}
      <p class="gcal"><a href="{html.escape(gcal_link(ev))}" target="_blank" rel="noopener">＋ Googleカレンダーに追加</a>
        <a href="ics/{event_uid(ev)}.ics">＋ Apple・Outlook用(.ics)</a></p>
    </article>"""


# ---- カレンダー(ICS購読フィード / Googleカレンダー追加リンク) ----
TIME_RE = re.compile(r"(\d{1,2}):(\d{2})")
PAREN_RE = re.compile(r"[(（][^)）]*[)）]")


def event_span(ev):
    """(終日か, 開始, 終了) を返す。終日のときの終了日は排他的(翌日)。
    時間は「15:30〜18:30」形式から読む。かっこ内(受付・開場など)は無視。
    単日で開始時刻だけなら1時間、時刻が読めない・複数日なら終日扱い。"""
    start, end = ev["_start"], ev["_end"]
    times = TIME_RE.findall(PAREN_RE.sub("", ev.get("time") or ""))
    if times and start == end:
        h, m = map(int, times[0])
        s = datetime.datetime.combine(start, datetime.time(h, m))
        e = s + datetime.timedelta(hours=1)
        if len(times) >= 2:
            h2, m2 = map(int, times[-1])
            e2 = datetime.datetime.combine(end, datetime.time(h2, m2))
            if e2 > s:
                e = e2
        return False, s, e
    return True, start, end + datetime.timedelta(days=1)


def event_details(ev) -> str:
    lines = []
    if (ev.get("time") or "").strip():
        lines.append("時間: " + ev["time"].strip())
    if ev.get("deadline"):
        lines.append("申込締切: " + ev["deadline"])
    if (ev.get("apply") or "").strip():
        lines.append("申込方法: " + ev["apply"].strip())
    url = source_url(ev.get("source", ""))
    if url:
        lines.append("情報源: " + url)
    lines.append("一覧: " + SITE_URL)
    return "\n".join(lines)


def gcal_link(ev) -> str:
    allday, s, e = event_span(ev)
    fmt = "%Y%m%d" if allday else "%Y%m%dT%H%M%S"
    q = urllib.parse.urlencode({
        "action": "TEMPLATE",
        "text": ev["name"],
        "dates": f"{s.strftime(fmt)}/{e.strftime(fmt)}",
        "details": event_details(ev),
        "ctz": "Asia/Tokyo",
    })
    return "https://calendar.google.com/calendar/render?" + q


def _ics_escape(text: str) -> str:
    return (text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\n", "\\n"))


def _ics_fold(line: str) -> str:
    """RFC 5545: 1行は75オクテットまで。超える分は半角スペース始まりの継続行にする。"""
    out, cur, size = [], "", 0
    for ch in line:
        n = len(ch.encode("utf-8"))
        if size + n > 75:
            out.append(cur)
            cur, size = " " + ch, 1 + n
        else:
            cur += ch
            size += n
    out.append(cur)
    return "\r\n".join(out)


def event_uid(e) -> str:
    return hashlib.sha1((e["name"] + e.get("eventDate", "")).encode("utf-8")).hexdigest()[:20]


def _vevent_lines(e):
    allday, s, en = event_span(e)
    lines = ["BEGIN:VEVENT", f"UID:{event_uid(e)}@kokugo-kenkyukai-info",
             "DTSTAMP:20260101T000000Z"]
    if allday:
        lines += [f"DTSTART;VALUE=DATE:{s.strftime('%Y%m%d')}",
                  f"DTEND;VALUE=DATE:{en.strftime('%Y%m%d')}"]
    else:
        lines += [f"DTSTART;TZID=Asia/Tokyo:{s.strftime('%Y%m%dT%H%M%S')}",
                  f"DTEND;TZID=Asia/Tokyo:{en.strftime('%Y%m%dT%H%M%S')}"]
    lines += [f"SUMMARY:{_ics_escape(e['name'])}",
              f"DESCRIPTION:{_ics_escape(event_details(e))}",
              "END:VEVENT"]
    return lines


def _ics_calendar(evs, calname=None) -> str:
    """calname を渡すと購読フィード用(名前・更新間隔つき)。なければ1件取り込み用。"""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//kokugo-kenkyukai-info//JA",
        "CALSCALE:GREGORIAN",
    ]
    if calname:
        lines += [
            "METHOD:PUBLISH",
            f"X-WR-CALNAME:{_ics_escape(calname)}",
            "X-WR-TIMEZONE:Asia/Tokyo",
            "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
            "X-PUBLISHED-TTL:PT12H",
        ]
    lines += [
        "BEGIN:VTIMEZONE",
        "TZID:Asia/Tokyo",
        "BEGIN:STANDARD",
        "DTSTART:19700101T000000",
        "TZOFFSETFROM:+0900",
        "TZOFFSETTO:+0900",
        "TZNAME:JST",
        "END:STANDARD",
        "END:VTIMEZONE",
    ]
    for e in evs:
        lines += _vevent_lines(e)
    lines.append("END:VCALENDAR")
    return "\r\n".join(_ics_fold(l) for l in lines) + "\r\n"


def build_ics(groups) -> str:
    evs = sorted(
        (e for g in groups.values() for e in g),
        key=lambda e: (e["_start"], e["_end"], e["name"]),
    )
    return _ics_calendar(evs, "国語科 学会・研究会")


def write_event_ics(groups):
    """予定ごとの .ics(1件だけカレンダーに追加したい人向け)を ics/ に書き出し、不要になったものは消す。"""
    ICS_DIR.mkdir(exist_ok=True)
    keep = set()
    for g in groups.values():
        for e in g:
            name = f"{event_uid(e)}.ics"
            keep.add(name)
            (ICS_DIR / name).write_bytes(_ics_calendar([e]).encode("utf-8"))
    for f in ICS_DIR.glob("*.ics"):
        if f.name not in keep:
            f.unlink()


def render_quick_table(groups) -> str:
    evs = sorted(
        (e for g in groups.values() for e in g),
        key=lambda e: (e["_start"], e["_end"], e.get("time") or "", e["name"]),
    )
    rows = "\n".join(
        f'<tr><td class="qt-when">{html.escape(fmt_date(e["_start"], e["_end"]))}</td>'
        f'<td class="qt-time">{html.escape((e.get("time") or "").strip())}</td>'
        f'<td><a href="#{e["_id"]}">{html.escape(e["name"])}</a></td></tr>'
        for e in evs
    )
    return f"""
  <section class="quick">
    <h2 class="category-title">開催日 早見表<span class="count">{len(evs)}件</span></h2>
    <table class="qt"><tbody>
{rows}
    </tbody></table>
  </section>"""


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
  .quick{{margin-bottom:38px;}}
  .qt{{width:100%;border-collapse:collapse;font-size:14px;}}
  .qt td{{padding:7px 10px;border-bottom:1px solid var(--rule);vertical-align:top;}}
  .qt-when{{white-space:nowrap;color:var(--indigo);font-weight:600;
    font-variant-numeric:tabular-nums;width:1%;}}
  .qt-time{{white-space:nowrap;color:var(--muted);font-variant-numeric:tabular-nums;width:1%;}}
  .qt a{{color:var(--ink);text-decoration:none;}}
  .qt a:hover{{text-decoration:underline;}}
  .card-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px;}}
  .card{{background:var(--paper-raised);border:1px solid var(--rule);border-radius:6px;
    box-shadow:var(--shadow);padding:16px 18px;}}
  .card-when{{font-size:12.5px;color:var(--indigo);font-weight:600;
    font-variant-numeric:tabular-nums;margin:0 0 6px;}}
  .card-title{{font-family:'Shippori Mincho B1',serif;font-size:16px;font-weight:700;
    margin:0 0 8px;text-wrap:balance;}}
  .deadline{{font-size:12px;color:var(--gold);margin:0 0 6px;}}
  .apply{{font-size:12.5px;margin:0 0 6px;word-break:break-all;}}
  .card-src{{font-size:11.5px;color:var(--muted);margin:8px 0 0;
    word-break:break-all;}}
  .card-src a{{color:var(--muted);}}
  .gcal{{font-size:11.5px;margin:6px 0 0;}}
  .gcal a{{color:var(--indigo);margin-right:12px;white-space:nowrap;}}
  .subscribe{{background:var(--indigo-soft);border:1px solid var(--rule);border-radius:6px;
    padding:12px 16px;margin:0 0 28px;font-size:13.5px;}}
  .sub-btns{{display:flex;flex-wrap:wrap;gap:10px;margin:10px 0 4px;}}
  .btn{{display:inline-block;padding:8px 16px;border-radius:6px;background:var(--indigo);color:var(--paper-raised);
    font-weight:600;font-size:13.5px;text-decoration:none;}}
  .subscribe details summary{{cursor:pointer;color:var(--muted);font-size:12.5px;margin-top:8px;}}
  .subscribe ul{{margin:8px 0 0;padding-left:1.4em;font-size:12.5px;color:var(--muted);}}
  .subscribe li{{margin:3px 0;}}
  .sub-url{{margin:8px 0 0;}}
  .subscribe code{{word-break:break-all;font-size:12px;}}
  .subscribe button{{font:inherit;font-size:12px;margin-left:6px;padding:2px 10px;border:1px solid var(--rule);
    border-radius:4px;background:var(--paper-raised);color:var(--ink);cursor:pointer;}}
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
  <div class="subscribe">
    <strong>📅 カレンダーに登録</strong>(登録すると、予定の追加・変更が自動で反映されます)
    <p class="sub-btns">
      <a class="btn" href="https://calendar.google.com/calendar/r?cid=webcal://upopotennis-gif.github.io/kokugo-kenkyukai-info/calendar.ics" target="_blank" rel="noopener">Googleカレンダーに登録</a>
      <a class="btn" href="webcal://upopotennis-gif.github.io/kokugo-kenkyukai-info/calendar.ics">Appleカレンダー(iPhone・Mac)に登録</a>
    </p>
    <details>
      <summary>ボタンで進まないとき(Apple カレンダー)</summary>
      <p class="sub-url"><code id="ics-url">https://upopotennis-gif.github.io/kokugo-kenkyukai-info/calendar.ics</code>
        <button type="button" id="ics-copy">URLをコピー</button></p>
      <ul>
        <li><strong>Mac</strong>: 「カレンダー」アプリのメニュー「ファイル」→「新規カレンダー照会…」→ URLを貼り付けて「照会」</li>
        <li><strong>iPhone / iPad</strong>: 「設定」→「カレンダー」→「アカウント」→「アカウントを追加」→「その他」→「照会するカレンダーを追加」→ URLを貼り付けて「次へ」→「保存」</li>
        <li>1件だけ追加したいときは、下の各予定の「Apple・Outlook用(.ics)」を押してください(自動更新はされません)。</li>
      </ul>
    </details>
    <script>
      document.getElementById("ics-copy").addEventListener("click", function () {{
        var url = document.getElementById("ics-url").textContent, btn = this;
        function done() {{ btn.textContent = "コピーしました"; }}
        if (navigator.clipboard) {{ navigator.clipboard.writeText(url).then(done, function () {{}}); }}
        else {{ var r = document.createRange(); r.selectNode(document.getElementById("ics-url")); getSelection().removeAllRanges(); getSelection().addRange(r); document.execCommand("copy"); done(); }}
      }});
    </script>
  </div>
  {quick}
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
    n = 0
    for c in ordered_categories:
        for e in groups[c]:
            n += 1
            e["_id"] = f"ev{n}"
    quick = render_quick_table(groups)
    sections = "\n".join(render_category(c, groups[c]) for c in ordered_categories)
    output = TEMPLATE.format(
        updated=today.isoformat(),
        total=total,
        quick=quick,
        sections=sections,
    )
    OUTPUT_PATH.write_text(output, encoding="utf-8")
    ICS_PATH.write_bytes(build_ics(groups).encode("utf-8"))
    write_event_ics(groups)
    print(f"Wrote {OUTPUT_PATH} ({total} upcoming events, {len(ordered_categories)} categories)")


if __name__ == "__main__":
    main()
