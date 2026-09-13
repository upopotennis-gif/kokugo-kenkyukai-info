# kokugo-kenkyukai-info

高校国語科向け 学会・研究会 開催情報まとめ(自動更新)

## これは何か

早稲田大学国語教育学会・全国大学国語教育学会・日本国語教育学会など、国語科教育に関わる学会公式サイトおよびメール案内を定期的に巡回し、新しく告知された学会・研究会・研修会・シンポジウムなどの開催情報を集約したサイトです。

公開ページ: GitHub Pages(Settings → Pages で有効化後、`https://<owner>.github.io/kokugo-kenkyukai-info/` に公開されます)

## 仕組み

- イベント情報の一次データは Notion データベースで管理し、重複チェック(既出イベントの除外)を行っています。
- `events.json` … Notion データベースの全件スナップショット
- `generate_site.py` … `events.json` を読み込み、開催日が本日以降のイベントのみを学会・団体別に分類し `index.html` を再生成するスクリプト
- `index.html` … 実際に公開される静的ページ(`generate_site.py` の出力。手編集しないでください)

「学会・研究会情報 週次収集」ルーティンが巡回のたびに、新着イベントを Notion に追記した上で `events.json` を更新し、`generate_site.py` を実行して `index.html` を再生成・push しています。

## 手動で再生成する場合

```bash
python3 generate_site.py            # 今日の日付を基準に再生成
python3 generate_site.py 2026-10-01 # 基準日を指定して再生成(確認用)
```
