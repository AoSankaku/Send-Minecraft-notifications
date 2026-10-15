# Send-Minecraft-notifications

Minecraft サーバーのログを監視し、起動・終了、プレイヤーの参加・退出、チャットなどを Discord の Webhook に通知します。Discord からのメッセージ取得や返信は行いません。

## すぐに使う（Python 不要）

1. [Releases](https://github.com/AoSankaku/Send-Minecraft-notifications/releases) から実行ファイルをダウンロードします。Windows x64 は `.exe`、Linux x64 は拡張子のない実行ファイルです。単体ファイルを使う場合、ZIP の展開は不要です。
2. 実行ファイルを任意のフォルダーに置いて起動します。この設定形式に対応したビルドでは、初回起動時に同じフォルダーへ `send-minecraft-notifications.toml` の雛形が作られます。
3. `send-minecraft-notifications.toml` の `WEBHOOK_URL` に Discord Webhook URL を、`TARGET_DIR` に Minecraft サーバーのログフォルダーを設定します。
4. 実行ファイルを再起動します。

公開済みの `v1.0.0-beta1` までの実行ファイルは従来どおり `.env` を使います。この設定ファイル名変更は、その後のビルドから利用できます。

今後のWindows版リリース実行ファイル名は、アプリ名・リリースタグ・対象OSが分かる `send-minecraft-notifications-<tag>-windows-x64.exe` 形式です（タグ内の `/` は `-` に置き換えます）。公開済みの beta0/beta1 のファイル名は変わりません。

<!-- smn:install-ja:start -->
対象リリース: [v1.0.0-beta1](https://github.com/AoSankaku/Send-Minecraft-notifications/releases/tag/v1.0.0-beta1)。Python のインストールや ZIP の展開は不要です。設定を書き込めるフォルダーで実行してください。

### Ubuntu Server / Linux x64 でのダウンロードと起動

```sh
curl -fL -o send-minecraft-notifications-linux-x64 \
  https://github.com/AoSankaku/Send-Minecraft-notifications/releases/download/v1.0.0-beta1/send-minecraft-notifications-linux-x64
```

任意で、実行前に同じリリースのチェックサムで検証します。未取得の ZIP は検査対象から外れます。

```sh
curl -fL -o SHA256SUMS-linux-x64.txt \
  https://github.com/AoSankaku/Send-Minecraft-notifications/releases/download/v1.0.0-beta1/SHA256SUMS-linux-x64.txt
sha256sum --check --ignore-missing SHA256SUMS-linux-x64.txt
```

実行権限を付けて初回起動します。同じフォルダーに `.env` の雛形を作成して終了します。

```sh
chmod +x ./send-minecraft-notifications-linux-x64
./send-minecraft-notifications-linux-x64
```

エディターで `.env` の `WEBHOOK_URL` と `TARGET_DIR`（Minecraft サーバーのログフォルダー）を設定してから、設定を検査して起動します。

```sh
./send-minecraft-notifications-linux-x64 --check-config
./send-minecraft-notifications-linux-x64
```

### Windows x64 / PowerShell でのダウンロードと起動

```powershell
curl.exe -fL -o smn-main-0ff73d1.exe `
  https://github.com/AoSankaku/Send-Minecraft-notifications/releases/download/v1.0.0-beta1/smn-main-0ff73d1.exe
.\smn-main-0ff73d1.exe
```

初回起動で作られた `.env` をエディターで開き、`WEBHOOK_URL` と `TARGET_DIR` を設定してから、次を実行します。

```powershell
.\smn-main-0ff73d1.exe --check-config
.\smn-main-0ff73d1.exe
```

`-L` は GitHub の転送先を追い、`-o` はファイルに保存し、`-f` は HTTP エラー時に失敗させます。既存の `.env` は上書きされません。設定検査では Discord へ送信しません。

### 旧Python版の .env を引き継ぐ

旧版の `.env` を `--config` で直接指定して起動できます。元の設定は変更されず、`TARGET_DIR` と `PLUGIN_DIR` の相対パスも旧 `.env` のフォルダーを基準に解決されます。設定を検査した後、同じ引数を付けて起動してください。パスは実際の旧版の場所へ置き換えます。

```sh
./send-minecraft-notifications-linux-x64 --config /path/to/Send-Minecraft-notifications/.env --check-config
./send-minecraft-notifications-linux-x64 --config /path/to/Send-Minecraft-notifications/.env
```

```powershell
.\smn-main-0ff73d1.exe --config 'C:\path\to\Send-Minecraft-notifications\.env' --check-config
.\smn-main-0ff73d1.exe --config 'C:\path\to\Send-Minecraft-notifications\.env'
```
<!-- smn:install-ja:end -->

### TOML設定の書き方（v1.0.0-beta1 の次のビルド以降）

Minecraftサーバーと同じフォルダーに置く場合、基本設定は次のようになります。Webhook URLは実際の値に置き換えてください。

```toml
WEBHOOK_URL = "https://discord.com/api/webhooks/..."
TARGET_DIR = "./logs"
TARGET_FILE = "latest.log"
```

文字列は引用符で囲み、ON/OFFは `true` / `false` で書きます。Windowsの絶対パスには `TARGET_DIR = 'C:\Minecraft\logs'` のように一重引用符を使うと、バックスラッシュをそのまま書けます。メッセージで改行したい場合は二重引用符で `"一行目\n二行目"` と書きます。一重引用符内の `\n` は文字のままです。

### 設定ファイルの場所を指定する（Windows / Linux 共通）

必要に応じて設定ファイルの場所を `--config <path>` で指定できます。`--init-config` は設定雛形を作成し、`--check-config` は設定を検査します。今後のWindows版リリースの実行ファイル名には、アプリ名・バージョン（リリースタグ）・対象OSを含めます。上のコマンドには公開済みの対象リリースの実際のファイル名を使用しています。

`TARGET_DIR` を相対パスで書いた場合は、`send-minecraft-notifications.toml` があるフォルダーからの相対パスとして解決されます。旧 `.env` を変換した場合も、そのファイルがあったフォルダーを基準にします。サーバー起動直後に `logs/latest.log` がまだ作られていなくても、ファイルが現れるまで待機します。

`send-minecraft-notifications.toml` には Webhook URL が含まれるため、公開や共有をしないでください。リリース ZIP に含まれるのは `send-minecraft-notifications.example.toml` のみです。

### 旧Python版の自動検出（v1.0.0-beta1 の次のビルド以降）

実行ファイルの横に `send-minecraft-notifications.toml` があればそれを使います。なければ、隣の旧 `.env` を同じフォルダーの `send-minecraft-notifications.toml` に自動変換します。元の `.env` はそのまま残り、以後はTOML設定が優先されます。旧Python版のフォルダーに新しい実行ファイルを置く方法でも引き継げます。

実行ファイルの横に設定がない場合、作業フォルダーの旧Python版を優先して検出します。そこに見つからなければ、実行ファイルと同じフォルダー内、またはその親フォルダー内にある `Send-Minecraft-notifications` を確認します。旧版のソースと `.env` が残っているフォルダーが対象です。複数の候補が見つかった場合は自動選択せず、`--config <旧フォルダー>` または `--config <旧.envのパス>` で指定してください。別の場所にある旧版も同じ方法で指定できます。

変換時は旧 `.env` を変更せず、同じフォルダーにTOMLを作成します。相対パスや設定値を引き継ぎ、新しく追加された未設定の項目には既定値を使います。明示した `--config` は自動検出より優先され、設定フォルダーまたは旧 `.env` ファイルを指定できます。`--init-config` は新しいTOML雛形を作成します。公開済みの `v1.0.0-beta0` と `v1.0.0-beta1` では、上のバージョン別手順のとおり `.env` を使います。

旧 `.env` の `${NAME}` は、同じファイル内で先に定義された値を参照できます。環境変数による設定の上書きは引き続き利用できますが、その値は変換先のTOMLには保存しません。

## 通知とメッセージ設定

- ログのチャットを含め、通知から Discord のユーザー、ロール、`@everyone` へのメンションは行われません。
- TOMLの二重引用符で囲んだ文字列に書いた `\n` は設定読込時に改行になります。
- メッセージテンプレートなど、追加の設定項目は `send-minecraft-notifications.example.toml` を参照してください。使わない任意項目は初期値のままにできます。

### 進捗・実績の翻訳と通知言語（v1.0.0-beta1 の次のビルド以降）

進捗・目標・挑戦・旧実績の名前を、Minecraftの言語データを使ってオフラインで翻訳します。既定は日本語です。Minecraft本体の解析、サーバーへのMod追加、外部翻訳APIは不要です。通知文も選択した言語になります。

```toml
LANGUAGE = "ja"
ADVANCEMENT_TRANSLATION_ENABLED = true
```

日本語では `Stone Age` を `石器時代`、旧実績の `Taking Inventory` を `所持品の確認` と表示します。翻訳できない名前は原文を残します。英語表示には `LANGUAGE = "en"` を指定します。設定を変更した後は通知プログラムを再起動してください。

| コード | 言語・地域 | コード | 言語・地域 |
| --- | --- | --- | --- |
| `ja` | 日本語 | `en` | 英語 |
| `zh-CN` | 中国語（簡体字・中国） | `zh-TW` | 中国語（繁体字・台湾） |
| `zh-HK` | 中国語（繁体字・香港） | `hi` | ヒンディー語 |
| `es` | スペイン語 | `fr` | フランス語 |
| `de` | ドイツ語 | `pt-BR` | ポルトガル語（ブラジル） |
| `pt-PT` | ポルトガル語（ポルトガル） | `ru` | ロシア語 |
| `ar` | アラビア語 | `id` | インドネシア語 |
| `ko` | 韓国語 | `vi` | ベトナム語 |
| `tr` | トルコ語 | `it` | イタリア語 |
| `pl` | ポーランド語 | `cs` | チェコ語 |
| `ms` | マレー語 | `ro` | ルーマニア語 |

`ja_jp`、`en_us`、`pt_br` などのMinecraft側のコードも利用できます。通知言語は1つを選択します。複数言語の同時配信は行いません。

Modやデータパック独自の名前、好みの訳は追加辞書で指定できます。キーはログに出る名前、値は選択した通知言語での表示です。完全一致で、同梱辞書より優先します。

```toml
LANGUAGE = "ja"
ADVANCEMENT_DICTIONARY = { "The Factory Must Grow!" = "工場を拡大せよ！" }
```

同梱データは `1.11.2`、`1.12.2`、`1.16.5`、`1.20.1`、`1.21.11`、`26.3` の公式言語リソースから作成しています。これは辞書の収録元であり、サーバーのバージョンを自動検出する機能ではありません。既定の `MINECRAFT_VERSION = ""` は、同じ翻訳キーについて最新の収録訳を使い、過去の英語名も認識します。収録版の訳に固定する場合は `MINECRAFT_VERSION = "1.20.1"` のように指定します。未収録の版は設定エラーになるため、通常は空欄のままにしてください。

通常ログには翻訳キーや進捗IDが残らないため、同じ英語名が別のキーで異なる訳を持つ場合は推測せず原文を残します。追加辞書で表示を指定できます。公式の訳がない項目や、未収録の新しい名前も原文のままです。旧版で存在しなかった言語・地域には、その版の翻訳がありません。任意のModや独自ログ書式への完全対応は保証していません。

名前の翻訳だけを止める場合は `ADVANCEMENT_TRANSLATION_ENABLED = false` にします。管理者が設定する `SERVER_START_MESSAGE`、`SERVER_STOP_MESSAGE`、`SERVER_RESTART_MESSAGE`、`TIPS_MESSAGES` は設定した文章のまま使用します。これらも必要に応じて選択言語の文章に変更してください。チャットのローマ字→日本語変換は、下記の `JAPANIZE_*` による独立した設定です。

通知テンプレートは、設定ファイルと同じフォルダーの `translations/<Minecraft言語コード>.json` で必要なキーだけ上書きできます。例：`translations/fr_fr.json` の `{"on_advancement_complete": ":trophy: %advancement-name% !"}`。未指定のキーは同梱の選択言語、そこにもなければ英語にフォールバックします。進捗名の追加辞書には `ADVANCEMENT_DICTIONARY` を使ってください。

言語データの取得元・更新手順は [Minecraft翻訳データ](translations/MINECRAFT_SOURCES.md) を参照してください。

### MOD由来の進捗・死亡メッセージと翻訳キャッシュ

`MODS_DIR` にサーバーの `mods` フォルダーを設定すると、起動時に直下のJARから言語ファイルと進捗定義を読み取ります。Createなど、MOD内に英語と選択言語の翻訳データがある進捗・目標・挑戦・旧実績名、および死亡メッセージに対応します。JARはZIP内のデータとして扱い、MinecraftやMODのJavaコードは実行しません。

```toml
LANGUAGE = "ja"
MODS_DIR = "./mods"
TRANSLATION_CACHE_DIR = "./translation-cache"
```

相対パスは設定ファイルがあるフォルダーを基準にします。別の場所のMODを読む場合は `MODS_DIR = 'D:\Minecraft\mods'` のように指定できます。`MODS_DIR = ""`（既定）ではMODを読み取らず、キャッシュも作成しません。

指定したキャッシュフォルダーは自動作成されます。JARの内容のSHA-256ごとにJSONを保存し、次回は展開・解析済みのデータを再利用します。内容を変更したMODは起動時に再解析し、削除したMODのキャッシュは参照しません。同じサイズ・更新日時でも内容の変更を検出します。第二言語範囲までの全22言語のデータをまとめて保持するため、`LANGUAGE` の変更だけでJARを再解析する必要はありません。

キャッシュには翻訳リソースを保存し、プレイヤーのチャット・ログ・Webhook URLは保存しません。キャッシュを削除しても次回起動時に再作成できます。削除済みMODなどの古いキャッシュファイルは自動削除しないため、必要なら通知プログラムを停止して整理してください。MODを入れ替えた場合は通知プログラムも再起動してください。

死亡メッセージは `%1$s` / `%2$s` / `%3$s` または `%s` の差し込み値を保持して翻訳します。プレイヤー名、攻撃者名、独自アイテム名は原文を保ちます。公式Createリソースでは、`Wheels of Destruction` → `破壊ホイール` と、破砕ホイールによる死亡文の変換を確認しています。MOD側に選択言語の訳がない場合、複数の解釈ができる場合、差し込み値が一致しない訳の場合は原文を残します。`ADVANCEMENT_DICTIONARY` の手動指定は、MOD由来の進捗名でも優先します。

壊れたJARや不正なリソースは警告し、読み取れる他のMODの処理を続けます。対応するのはJAR内の `.json` / 旧 `.lang` 言語リソースとデータ定義から特定できるメッセージです。外部リソースパックの翻訳、入れ子JAR、コードだけで動的生成される任意の診断ログまで自動翻訳する機能ではありません。設定確認とキャッシュ作成には、通知を送信しない `--check-config` を利用できます。

### ローマ字チャットの日本語表示（v1.0.0-beta1 の次のビルド以降）

`send-minecraft-notifications.toml` に次を追加して再起動すると、Discordへ原文と日本語変換を併記します。既存の設定に追加しなければ無効のままです。

```toml
JAPANIZE_ENABLED = true
JAPANIZE_MODE = "auto"
```

表示例（プレイヤー名・アイコンはそのまま使用）:

```text
konnichiha
↳ こんにちは
```

| モード | 動作 |
| --- | --- |
| `auto`（既定） | 同じ公開チャットのログにあるサーバーの変換結果を優先し、なければローカル変換します。 |
| `local` | サーバーが併記した変換結果があっても、原文からこのツールで変換します。 |
| `server` | ログにある変換結果だけを利用します。なければ原文だけを送信します。 |

独自変換はローマ字からひらがなへの変換で、API、翻訳サービス、オンライン辞書へ本文を送りません。一般的なかな漢字変換は行いませんが、任意のローカル辞書で漢字や固有名詞を指定できます。辞書はローマ字の単語または発言全体に一致するものを使います。

```toml
JAPANIZE_DICTIONARY = { "maikura" = "マイクラ", "ohayou gozaimasu" = "おはようございます" }
```

日本語が含まれる発言、`/` または `$` で始まる発言は独自変換しません。URL、メール、メンション、コード、`minecraft:stone` のようなIDは変換対象から除外します。英単語とローマ字は厳密に判別できないため、変換が不要な発言には `$` を付けてください。原文と変換文の両方でDiscordメンションは禁止し、長文は上限内に分割します。

Minecraft Java版のバージョン番号やMod APIには依存せず、Vanilla/Fabricの通常ログ、Forge/NeoForgeのロガー付きログ、Paper/Spigotの非同期チャット、旧形式のINFOログを読みます。バージョン別の導入物は不要です。任意のプラグイン書式まで自動判別できるわけではなく、実機で全バージョンを起動検証したものではありません。チャット本文が `<Player> message` の形式ならスレッド名に依存せず認識します。`Player: message` はチャット用スレッドまたはLunaChatロガーと分かる行に限定して認識し、サーバーの診断表示と混同しません。スレッド情報のない独自書式では、サーバー側の公開チャット書式を `<%username> %msg` などにしてください。

LunaChatの既定の1行書式 `原文 (変換文)` と、Tsuki Chatの同一ログレコード内の `原文`＋改行＋`→ 変換文` に対応します。LunaChatでは `displayNormalChatOnConsole: true` と `japanizeDisplayLine: 1` にすると、原文と変換を同じ行から取得できます。別の本文書式には、次のように2つの項目を各1回含むテンプレートを指定できます。テンプレートは正規表現ではありません。

```toml
JAPANIZE_SERVER_FORMAT = "{original} => [{japanese}]"
```

送信者のない別ログの `[JP] ...` や `→ ...` は、私信や別プレイヤーの変換の可能性があるため推測して結び付けません。その場合、`auto` は元の公開チャットから独自変換します。ゲーム内だけに表示されてログに残らない変換結果も取得できません。サーバー側プラグイン自身の外部通信設定は、このツールの設定とは別です。上流の書式は [LunaChatの設定](https://github.com/ucchyocean/LunaChat/blob/f8bf6e036354a0f04f23059ba6de8da6e9a9fca0/src/main/resources/config.yml) と [Tsuki Chatのログに渡す文字列](https://github.com/Meatwo310/tsuki-chat/blob/460f30b02b4b7a13fc9e396cd5f1adc8e295e8ec/1.20.1/forge/src/main/java/net/meatwo310/tsukichat/util/ChatCustomizer.java#L66) を参照してください。

チャンネル名から公開・非公開は判別できないため、名前付きチャンネルは既定では転送しません。公開と確認したチャンネルだけを明示します。私信の `[Player -> Target] ...` や、許可していない／識別できないチャンネル書式は除外します。

```toml
JAPANIZE_PUBLIC_CHANNELS = ["global"]
```

### システム通知のアイコン

起動・終了、参加・退出、コンソールの発言、定期案内などのシステム・サーバー通知には、既定で自作の情報アイコン [info_icon_dot.png](assets/info_icon_dot.png) を使用します。特定プレイヤーのスキンを初期値には使用しません。画像はこのリポジトリの `main/assets/info_icon_dot.png` の固定Raw URLからDiscordが取得します。

管理者はTOML設定で次のように変更できます。優先順位は `SENDER_ICON`、`SENDER_ICON_PLAYER`、既定の情報アイコンの順です。

| 設定 | 使用するアイコン |
| --- | --- |
| 両方空欄（または未設定） | 既定の情報アイコン |
| `SENDER_ICON="https://example.com/icon.png"` | 指定した画像URL |
| `SENDER_ICON=""` と `SENDER_ICON_PLAYER="PlayerName"` | 明示指定したMinecraftプレイヤーのアイコン（`PLAYER_ICON_API` を使用） |

旧 `.env` にプレイヤーのスキンURLが設定されている場合、既定の情報アイコンへ切り替えるには `SENDER_ICON` を空欄にしてください。プレイヤー本人のチャットには引き続きそのプレイヤーのアイコンを使用します。設定を変更した後は通知プログラムを再起動してください。

開発用の未公開ブランチでは、既定アイコンの画像を `main` に公開するまでRaw URLは利用できません。別の公開画像を使う場合は `SENDER_ICON` にそのURLを設定してください。

## 対応する配布ビルド

現在のリリースビルドは Windows x64 と Ubuntu 22.04 x64 で作成します。Linux x64 版は Ubuntu 22.04・24.04 で、Python を PATH に含めない環境での初回起動・設定検査を確認しています。Linux バイナリは glibc 2.35 以降を必要とします。ほかの OS、Linux ディストリビューション、CPU アーキテクチャでの互換性は保証していません。PyInstaller の one-file 実行ファイルは、起動時に内部ファイルを一時フォルダーへ展開します。

## 開発者向け

開発には Python 3.12 と [uv](https://docs.astral.sh/uv/) を使います。

実行前に `send-minecraft-notifications.example.toml` を `send-minecraft-notifications.toml` にコピーし、`WEBHOOK_URL` と `TARGET_DIR` を設定してください。

```sh
uv sync --frozen
uv run pytest
uv run python src/main.py
```

配布ビルドを作るときは、ビルドする OS 上で次を実行します。OS ごとのバイナリはそれぞれの OS 上でビルドしてください。

```sh
uv sync --frozen --group build
uv run python scripts/build_release.py --version v1.2.3
```

`v1.2.3` は配布するバージョンまたはタグに置き換えてください。PC内でデバッグ用にビルドする場合は `--version` を付けずに実行します。ローカルのWindowsデバッグ用EXEだけは、アプリ名・ブランチ名・短いコミットハッシュを含む28文字以内の名前になります。

生成物は `dist/release/` に作成されます。単体バイナリ、バイナリと README・LICENSE・`send-minecraft-notifications.example.toml` をまとめた ZIP、SHA-256 チェックサムが入ります。

## GitHub Actions による自動リリース

リリースタグを GitHub に push すると、Windows x64 と Linux x64 のビルドが自動で実行されます。`1.2.3`・`v1.2.3` のどちらの形式も使えます。このリポジトリではすべてのタグをリリースとして扱います。タグ名は英数字で始め、英数字と `.`, `_`, `/`, `+`, `-` を使用してください。タグの対象コミットに `.github/workflows/release.yml` が含まれている必要があります。

両 OS のテスト・単体実行チェックが成功した後、成果物のチェックサムを検証し、実行ファイル・ZIP・チェックサムの計6ファイルを同じ GitHub Release へ添付して自動公開します。リリースノートには変更履歴に加え、そのタグと実際の Windows ファイル名に合った Linux / PowerShell のダウンロード・設定・起動手順を日英で自動挿入します。配布 ZIP 内の README にも同じタグの手順を収録します。

公開後、既定ブランチの README の手順部分だけを GitHub Actions が更新します。最も新しく公開されたリリースを対象とし、古いリリースの再実行で URL を巻き戻しません。既定ブランチが直接更新を禁止している場合、この更新ステップは失敗するため、ブランチルールに応じた運用が必要です。手順の生成元は `scripts/release_docs.py` です。`smn:install-ja` / `smn:install-en` のコメントで囲んだ部分は自動生成されるので、文言を変更する場合は生成元を編集してください。

アップロード完了までは Draft 状態を維持し、途中で失敗した場合は公開しません。再実行では途中の Draft を完成させ、公開済みのリリースの添付ファイルは変更しません。README 更新が失敗しても、公開済みの実行ファイルは利用できます。

`1.2.3-rc.1`・`v1.2.3-beta.1` のようなタグは Prerelease として公開します。ベータタグでは Docker の `latest` タグを更新しません。追加のトークン設定は不要で、公開ジョブに限定した `GITHUB_TOKEN` の `contents: write` 権限を使用します。Actions からの手動実行はビルドと Actions artifact の作成のみで、リリースは公開しません。

## English

Download the Windows x64 `.exe` or Linux x64 binary from [Releases](https://github.com/AoSankaku/Send-Minecraft-notifications/releases). The standalone binary does not require Python, and you can run it without extracting a ZIP. Builds after the published `v1.0.0-beta1` create `send-minecraft-notifications.toml` beside the executable on first run. Set `WEBHOOK_URL` and `TARGET_DIR`, then run it again. Relative paths are resolved from the configuration file's folder. On Linux, run `chmod +x <binary>` first. The Linux build requires glibc 2.35 or newer. Other operating systems and architectures are not currently supported release targets.

<!-- smn:install-en:start -->
Release: [v1.0.0-beta1](https://github.com/AoSankaku/Send-Minecraft-notifications/releases/tag/v1.0.0-beta1). No Python installation or ZIP extraction is required. Run these commands in a writable directory.

### Ubuntu Server / Linux x64 download and startup

```sh
curl -fL -o send-minecraft-notifications-linux-x64 \
  https://github.com/AoSankaku/Send-Minecraft-notifications/releases/download/v1.0.0-beta1/send-minecraft-notifications-linux-x64
```

Optionally verify the checksum before execution. The ZIP is ignored if it was not downloaded.

```sh
curl -fL -o SHA256SUMS-linux-x64.txt \
  https://github.com/AoSankaku/Send-Minecraft-notifications/releases/download/v1.0.0-beta1/SHA256SUMS-linux-x64.txt
sha256sum --check --ignore-missing SHA256SUMS-linux-x64.txt
```

Make the binary executable, then run it once to create a `.env` template beside it and exit.

```sh
chmod +x ./send-minecraft-notifications-linux-x64
./send-minecraft-notifications-linux-x64
```

Use an editor to set `WEBHOOK_URL` and `TARGET_DIR` (your Minecraft server's log directory) in `.env`. Validate the settings, then start the notifier:

```sh
./send-minecraft-notifications-linux-x64 --check-config
./send-minecraft-notifications-linux-x64
```

### Windows x64 / PowerShell download and startup

```powershell
curl.exe -fL -o smn-main-0ff73d1.exe `
  https://github.com/AoSankaku/Send-Minecraft-notifications/releases/download/v1.0.0-beta1/smn-main-0ff73d1.exe
.\smn-main-0ff73d1.exe
```

Open the generated `.env` in an editor and set `WEBHOOK_URL` and `TARGET_DIR`, then run:

```powershell
.\smn-main-0ff73d1.exe --check-config
.\smn-main-0ff73d1.exe
```

`-L` follows GitHub redirects, `-o` saves to a file, and `-f` fails on HTTP errors. Existing `.env` files are preserved. Configuration checks do not send Discord notifications.

### Reuse a legacy Python .env

Pass the old `.env` to `--config` to reuse it without modifying it. Relative `TARGET_DIR` and `PLUGIN_DIR` paths remain based on the old `.env` directory. Validate first, then start with the same argument each time. Replace the example paths with your old installation's location.

```sh
./send-minecraft-notifications-linux-x64 --config /path/to/Send-Minecraft-notifications/.env --check-config
./send-minecraft-notifications-linux-x64 --config /path/to/Send-Minecraft-notifications/.env
```

```powershell
.\smn-main-0ff73d1.exe --config 'C:\path\to\Send-Minecraft-notifications\.env' --check-config
.\smn-main-0ff73d1.exe --config 'C:\path\to\Send-Minecraft-notifications\.env'
```
<!-- smn:install-en:end -->

### Configuration file

Builds after `v1.0.0-beta1` create `send-minecraft-notifications.toml` beside the executable on first run when no settings are found. Set `WEBHOOK_URL` and `TARGET_DIR` in this file. Keep it private because it contains the Discord webhook URL; the release ZIP contains only `send-minecraft-notifications.example.toml`. Pass either a configuration directory or a TOML/legacy `.env` file to `--config`; `--init-config` creates the named TOML file.

For a notifier placed beside the Minecraft server, use the following settings, replacing the webhook URL:

```toml
WEBHOOK_URL = "https://discord.com/api/webhooks/..."
TARGET_DIR = "./logs"
TARGET_FILE = "latest.log"
```

Quote strings and use `true` / `false` for switches. Single quotes preserve Windows backslashes, for example `TARGET_DIR = 'C:\Minecraft\logs'`. Double-quoted message strings support escapes: `"first\nsecond"` contains a line break; single-quoted `'first\nsecond'` keeps the literal backslash and `n`. Legacy `${NAME}` references can use earlier values from the same `.env` file. Process environment overrides remain supported at runtime and are never saved during migration.

### Windows executable names

Future Windows releases use `send-minecraft-notifications-<tag>-windows-x64.exe`, so the asset identifies the app, exact release tag, and platform. A `/` in a tag is replaced by `-` in the filename. The already published `v1.0.0-beta0` and `v1.0.0-beta1` assets keep their existing names. Local builds without `--version` use a compact debug filename containing the app, branch, and short commit hash (up to 28 characters). To build locally with the public release naming format, pass the tag, for example `uv run python scripts/build_release.py --version v1.2.3`; GitHub Actions uses the pushed tag automatically.

### Japanese chat (builds after v1.0.0-beta1)

Add these settings to `send-minecraft-notifications.toml` and restart to show original chat and Japanese text together. Missing settings default to disabled:

```toml
JAPANIZE_ENABLED = true
JAPANIZE_MODE = "auto"
```

`auto` reuses a Japanese result from the same public-chat record, otherwise converts locally. `local` always converts the original locally; `server` only uses recorded server results. Independent conversion is offline romaji-to-hiragana, without conversion APIs, model downloads, or dictionary services. It does not perform general kana-to-kanji conversion. Optional exact-word or whole-message dictionary entries can supply kanji and proper names:

```toml
JAPANIZE_DICTIONARY = { "maikura" = "マイクラ", "ohayou gozaimasu" = "おはようございます" }
JAPANIZE_SERVER_FORMAT = ""
JAPANIZE_PUBLIC_CHANNELS = []
```

Messages already containing Japanese or beginning with `/` or `$` skip local conversion. URLs, emails, mentions, code, and namespaced IDs remain intact. Romaji cannot always be distinguished from English; prefix a message with `$` to skip conversion. Mentions remain disabled in both lines, and long player messages are split within Discord's limit.

Common Vanilla/Fabric, Forge/NeoForge, Paper/Spigot async, and old INFO log layouts are supported without depending on a Minecraft version number or installing a version-specific mod. This is log-format compatibility, not a complete Minecraft runtime test matrix. Angle-style `<Player> message` works across these layouts. Colon-style `Player: message` requires a chat thread or LunaChat logger; for custom logs without that provenance, use an unambiguous public-chat server format such as `<%username> %msg`.

LunaChat's default single-line `original (Japanese)` and Tsuki Chat's same-record `original` followed by an unprefixed `→ Japanese` continuation are recognized. For LunaChat, enable normal console chat and single-line Japanize display. A custom `JAPANIZE_SERVER_FORMAT` must contain `{original}` and `{japanese}` once each, for example `{original} => [{japanese}]`; it is a literal template. Anonymous separate `[JP]` / arrow records may belong to private messages and are never guessed or forwarded. Results visible only in-game cannot be recovered from logs; `auto` falls back to local conversion. The server plugin's own network settings are independent of this tool.

Named channels are excluded by default because a name does not prove a channel is public. Only list channels you have verified are public, e.g. `JAPANIZE_PUBLIC_CHANNELS = ["global"]`. Private-message and unrecognized channel layouts remain excluded.

### Advancement translation and notification languages (builds after v1.0.0-beta1)

Set `LANGUAGE = "ja"` (the default) or one of `en`, `zh-CN`, `zh-TW`, `zh-HK`, `hi`, `es`, `fr`, `de`, `pt-BR`, `pt-PT`, `ru`, `ar`, `id`, `ko`, `vi`, `tr`, `it`, `pl`, `cs`, `ms`, `ro`. Minecraft aliases such as `en_us` and `pt_br` are also accepted. One language is selected for event notifications and advancement, goal, challenge, and legacy achievement names. Restart after changing configuration.

Translation uses bundled, official Minecraft language data offline, with no game decompilation, server mod, or translation API. `ADVANCEMENT_TRANSLATION_ENABLED = false` preserves original names while keeping the selected event language. Unknown names and names with conflicting translations across different keys stay unchanged. `ADVANCEMENT_DICTIONARY = { "Custom English Title" = "Your translation" }` provides exact overrides for the currently selected language, including mod/datapack names.

Bundled source snapshots are `1.11.2`, `1.12.2`, `1.16.5`, `1.20.1`, `1.21.11`, and `26.3`; these are dictionary sources, not an automatically detected server version or a runtime compatibility matrix. The default `MINECRAFT_VERSION = ""` recognizes historical English aliases and uses the newest available wording for each translation key. Set a bundled version explicitly to use its exact translations. Unsupported explicit versions are configuration errors. Some older locales or entries have no official translation; missing translations remain unchanged. No complete coverage of arbitrary mods or custom log formats is promised.

Administrator-written `SERVER_START_MESSAGE`, `SERVER_STOP_MESSAGE`, `SERVER_RESTART_MESSAGE`, and `TIPS_MESSAGES` stay as configured; change their text separately when needed. `JAPANIZE_*` chat conversion settings remain independent. A local `translations/<Minecraft-locale>.json` beside the config can override individual event templates; missing keys fall back to the bundled selected language and then English. See [data sources and maintenance](translations/MINECRAFT_SOURCES.md).

### MOD resources and persistent translation cache

Set `MODS_DIR = "./mods"` to scan direct child mod JARs at startup, and optionally set `TRANSLATION_CACHE_DIR = "./translation-cache"`. Both paths are relative to the configuration file. Empty `MODS_DIR` (the default) disables the scan and does not create a cache. JARs are read as ZIP data only; no Minecraft or Java/mod code runs. The application remains offline.

Language JSON/legacy `.lang` files and advancement definitions identify mod advancement, goal, challenge, legacy achievement and death messages. Extracted resources for all 22 supported locales are stored in automatically created JSON cache files keyed by the JAR's content SHA-256. Restarting reuses unchanged extraction results; changed content is detected even when size and modification time match. Changing only `LANGUAGE` reuses the same extraction cache. Removed mods stop contributing translations; their unused cache files are left intact. Restart the notifier after modifying mods. The cache contains resource translations, not chat, player logs or webhook credentials, and can be deleted to force regeneration.

Death templates support positional `%1$s`–`%3$s`, sequential `%s` and literal `%%`, retaining player/attacker/custom item names as literal values. Missing translations, conflicting interpretations or incompatible argument sets preserve the original. Exact `ADVANCEMENT_DICTIONARY` overrides take priority for mod titles too. Create's official resource data was checked for the “Wheels of Destruction” advancement and Crushing Wheels death message; this is resource verification, not a game/runtime test matrix.

Malformed JARs/resources produce warnings while valid siblings continue. Nested JARs, translations supplied only by external resource packs and arbitrary diagnostics constructed entirely in code are outside this resource-based lookup. `--check-config` also validates the configured folders and prepares the cache without sending notifications.

### Additional configuration

Builds after `v1.0.0-beta1` use `send-minecraft-notifications.toml` beside the executable. When an old `.env` is selected or discovered, it is converted to TOML in the same folder and preserved; later runs prefer TOML. If no adjacent settings exist, the tool checks the working directory for a legacy Python checkout, then checks folders named `Send-Minecraft-notifications` inside the executable's directory and its parent. The old source files and `.env` must still be present for this discovery. If several neighboring checkouts are found, select one with `--config <old-directory>` or `--config <old-.env-path>`. Explicit `--config` takes priority. Missing new settings use defaults. `--init-config` creates a new named TOML template instead of detecting another installation. Published `v1.0.0-beta0` and `v1.0.0-beta1` binaries still use `.env` and their versioned instructions above.

System/server notifications use the original [info icon](assets/info_icon_dot.png) from this repository's fixed `main/assets/info_icon_dot.png` Raw URL by default; no player's skin is used as the default. Leave `SENDER_ICON` and `SENDER_ICON_PLAYER` empty or unset to use it. Administrators can set `SENDER_ICON` to a custom image URL, or leave it empty and set `SENDER_ICON_PLAYER` to a Minecraft player name to use that player's icon through `PLAYER_ICON_API`. An explicit image URL takes priority over a player name. Existing icon URLs remain supported; clear the old URL to switch to the default. Player chat continues to use each player's own icon. Restart the notifier after changing settings. The default image must be published to `main` before its Raw URL is available.

For development, install Python 3.12 and uv, copy `send-minecraft-notifications.example.toml` to `send-minecraft-notifications.toml`, and set `WEBHOOK_URL` and `TARGET_DIR`. Then run `uv sync --frozen`, `uv run pytest`, and `uv run python src/main.py`. To build on the target operating system, run `uv sync --frozen --group build` followed by `uv run python scripts/build_release.py`. Omitting `--version` produces the compact local debug filename; pass `--version <tag>` to produce the public versioned name.

Pushing a release tag (for example `1.2.3` or `v1.2.3`) runs both platform builds and publishes one GitHub Release containing both binaries, ZIPs, and checksums after tests and asset verification succeed. Tag names must start with an ASCII letter or digit and contain only ASCII letters, digits, `.`, `_`, `/`, `+`, or `-`. The tagged commit must include the release workflow. Each ZIP's README and the release notes include generated Linux and PowerShell installation commands using that release's tag and actual Windows filename. After publication, Actions updates only the managed installation sections of the default branch's README. Older release reruns cannot roll the URLs back. Branch rules must allow this README update; if it fails, the published binaries remain available. Edit `scripts/release_docs.py` to change instructions inside the `smn:install-ja` / `smn:install-en` markers.

Version tags with a suffix such as `-rc.1` publish a prerelease and do not update Docker's `latest` tag. Failed uploads remain drafts; reruns complete drafts while preserving published releases. Manual workflow runs create Actions artifacts only. No additional token is required.

## License

MIT. See [LICENSE](LICENSE).
