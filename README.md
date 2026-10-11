# kokugo-kenkyukai-info

高校国語科向け 学会・研究会 開催情報まとめ(毎日自動更新)

公開ページ: https://upopotennis-gif.github.io/kokugo-kenkyukai-info/

## これは何か

早稲田大学国語教育学会・全国大学国語教育学会・日本国語教育学会など、国語科教育に関わる学会公式サイトおよびメール案内を巡回し、新しく告知された学会・研究会・研修会・シンポジウムなどの開催情報を集約したサイトです。

- 開催日・時間・申込締切・申込方法を一覧(団体別カード + 開催日の早見表)で表示
- カレンダーに登録(購読)でき、予定の追加・変更が自動で反映されます
  - 購読URL: `https://upopotennis-gif.github.io/kokugo-kenkyukai-info/calendar.ics`
  - 1件だけ追加したいときは、各カードの「Googleカレンダーに追加」「Apple・Outlook用(.ics)」

## 仕組み

イベント情報の一次データは Notion データベース「学会・研究会 既出イベント一覧」で管理し、重複チェックと更新履歴(ChangeLog)を持たせています。

| ファイル | 役割 |
|---|---|
| `events.json` | Notion データベースの全件スナップショット(`name` / `eventDate` / `time` / `deadline` / `apply` / `source`) |
| `generate_site.py` | `events.json` から `index.html`・`calendar.ics`・`ics/` を再生成するスクリプト(開催日が本日以降のものだけを掲載) |
| `index.html` | 公開ページ(生成物。手編集しないでください) |
| `calendar.ics` | 全予定の購読フィード(生成物) |
| `ics/` | 予定ごとの `.ics`(1件取り込み用。生成物。不要になったものは自動削除) |
| `hidden.json` | **サイトとカレンダーに出さない**イベント名の一覧(Notion には残すので、重複追加は起きません) |

### 更新ルーティン

Claude Code のルーティン「学会・研究会情報 毎日収集（GitHub Pages・カレンダー公開）」が、毎日 20:00(日本時間)に次を行い、変更があれば `main` に push します。

1. 学会公式サイト(9件)と Gmail(直近14日)から、新着イベントと既存イベントの更新(締切・時間・申込方法・出典URL)を探す
2. Notion に追記・更新(更新したときは `LastUpdated` と `ChangeLog` を記録)
3. 全件を `events.json` に書き出し、`generate_site.py` を実行
4. `events.json` / `index.html` / `calendar.ics` / `ics/` をコミット・push

### 掲載ルール

- 情報源は URL のときだけ表示(メール由来は表示しません)。申込方法は申込フォームのURL・申込先メールアドレス・申込サイトのみ載せます(Zoom の URL・パスコード・電話番号は載せません)。
- 時間が分からない予定は、カレンダーでは終日として入ります。終了時刻が不明な予定(`17:00〜` など)は1時間の枠で入ります。

## 手動で再生成する場合

```bash
python3 generate_site.py            # 今日の日付を基準に再生成
python3 generate_site.py 2026-10-01 # 基準日を指定して再生成(確認用)
```
