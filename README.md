# Redash 利用実績CSV

ChatGPTデスクトップのWorkから、指定した組織の日別利用時間をCSVに出力します。出力は組織・スペース名・ユーザー名ごとのピボットで、単位は分です。

## 初回だけ

1. ChatGPTデスクトップの **Work** にチームのセットアップガイドのURLを貼り、「このページの手順に従って、このスキルをローカルで使えるようにして」と頼みます。チームガイドがなければ、このREADMEのURLと同じ依頼文を送ります。
2. Workが専用フォルダの作成、ファイル配置、Pythonの確認、`.env` の初期化を進めます。ローカルアクセスやPythonのインストールに本人の操作が必要な場合は、Workの案内に従います。
3. Workが案内した **`.env`** を開き、`REDASH_USER_API_KEY=` の右側に自分のRedash User API Keyを入力します。チームの共通設定がなければ、`REDASH_BASE_URL` と `REDASH_QUERY_ID` も入力します。

## 毎回の使い方

Workで同じフォルダを開き、たとえば「このフォルダのSKILL.mdを使って、組織ID 12345の直近30日分のRedash利用実績をCSVにして」と頼みます。日付で範囲を指定することもできます。CSVは作業フォルダの `csv/` に保存されます。

## Work向けセットアップ手順

1. ローカル実行で、利用者のホームフォルダ直下に専用の `Redash利用実績` フォルダを用意します。共有・同期フォルダや既存のGitリポジトリの外に作ります。
2. 次のファイルをこのリポジトリの同じリビジョンから取得し、作業フォルダに配置します。チームのガイドでリビジョンが指定されている場合は、その指定を使います。
   - [SKILL.md](.agents/skills/redash-usage-pivot/SKILL.md) を直下に保存します。
   - [export_usage.py](.agents/skills/redash-usage-pivot/scripts/export_usage.py) を `scripts/` に保存します。
   - [空欄ひな形](.agents/skills/redash-usage-pivot/assets/.env.example) を `assets/.env.example` に保存します。
3. チームガイドに共通設定があれば、直下の `redash-team.env.example` に保存します。APIキーの欄は空欄にします。
4. 保存した `SKILL.md` の「初回セットアップ」に従い、ローカルのPythonを確認して `.env` を初期化します。作業フォルダと `.env` の場所を利用者に案内します。

Workはローカルに保存した `SKILL.md` を読み、スクリプトを実行します。ChatGPTのスキル一覧への登録は不要です。WorkからのセットアップとCSV保存までの実機確認は未実施です。 [ChatGPT Workのローカルフォルダ](https://help.openai.com/en/articles/20001275-chatgpt-work-and-codex)

## Redashの設定

`REDASH_BASE_URL` には、APIがリダイレクトせずに応答するHTTPSのベースURLを指定します。クエリは `org_id`、`期間`（日付範囲）、`集計`（値は `DAY`）を受け取り、`period`、`org_id`、`space_name`、`user_name`、`duration_min` をCSVで返す必要があります。指定した組織以外の行が返った場合は、CSVを保存せずエラーを返します。
