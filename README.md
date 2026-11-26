# Redash 利用実績CSV

ChatGPTデスクトップのWorkから、指定した組織の日別利用時間をCSVに出力します。出力は組織・スペース名・ユーザー名ごとのピボットで、単位は分です。

## 初回だけ

1. 自分の端末に、このスキル専用のローカル作業フォルダ（例 `Redash利用実績`）を作ります。共有・同期フォルダや既存のGitリポジトリの外に作成してください。チームから受け取った `redash-team.env.example` をそのフォルダに置き、ChatGPTデスクトップの **Work** で開きます。ChatGPTのスキル一覧から **Redash 利用実績CSV** をインストールします。
2. Workに「Redash 利用実績CSVの初期設定をして」と頼みます。Pythonが見つからなければ、[Python公式サイト](https://www.python.org/downloads/) からPython 3をインストールし、もう一度初期設定を頼みます。macOSでは `python3 --version`、Windowsでは `py -3 --version` で確認できます。Windowsで `py` が使えない場合は `python --version` も確認できます。
3. Workが作成した `.env` をテキストエディタで開き、`REDASH_USER_API_KEY=` の右側に自分のRedash User API Keyを入力します。チームのひな形を使わない場合は、`REDASH_BASE_URL` と `REDASH_QUERY_ID` も入力します。

## 毎回の使い方

Workで同じローカルフォルダを開き、例えば「Redash 利用実績CSVで、組織ID 12345の直近30日分を出して」と頼みます。日付で範囲を指定することもできます。CSVは作業フォルダの `csv/` に保存されます。

## 配布担当者向け

公開用の [空欄ひな形](.agents/skills/redash-usage-pivot/assets/.env.example) を `redash-team.env.example` としてコピーし、チーム共通のURLとクエリIDだけを書いて社内で配布できます。利用者は、自分のキーを初回にローカルの `.env` に入力します。

`REDASH_BASE_URL` には、APIがリダイレクトせずに応答するHTTPSのベースURLを指定します。クエリは `org_id`、`期間`（日付範囲）、`集計`（値は `DAY`）を受け取り、`period`、`org_id`、`space_name`、`user_name`、`duration_min` をCSVで返す必要があります。指定した組織以外の行が返った場合は、CSVを保存せずエラーを返します。

スキル本体は [SKILL.md](.agents/skills/redash-usage-pivot/SKILL.md) と同じフォルダにあります。ChatGPTワークスペースに登録する際は、そのフォルダをZIPにしてスキルとしてアップロードし、対象メンバーに共有します。Workのローカル利用とスキルの共有が、そのメンバーのワークスペース設定で許可されている必要があります。配布前に、Workからの初期設定、各自のRedashキーでの取得、CSVの保存を端末1台で確認します。 [ChatGPTのスキル共有](https://help.openai.com/en/articles/20001066-skills-in-chatgpt)
