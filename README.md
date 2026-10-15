# Send-Minecraft-notifications

Minecraft サーバーのログを監視し、起動・終了、プレイヤーの参加・退出、チャットなどを Discord の Webhook に通知します。Discord からのメッセージ取得や返信は行いません。

## すぐに使う（Python 不要）

1. [Releases](https://github.com/AoSankaku/Send-Minecraft-notifications/releases) から実行ファイルをダウンロードします。Windows x64 は `.exe`、Linux x64 は拡張子のない実行ファイルです。単体ファイルを使う場合、ZIP の展開は不要です。
2. 実行ファイルを任意のフォルダーに置いて起動します。初回起動時に同じフォルダーへ `.env` の雛形が作られます。
3. `.env` の `WEBHOOK_URL` に Discord Webhook URL を、`TARGET_DIR` に Minecraft サーバーのログフォルダーを設定します。
4. 実行ファイルを再起動します。

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

### 設定ファイルの場所を指定する（Windows / Linux 共通）

必要に応じて設定ファイルの場所を `--config <path>` で指定できます。`--init-config` は設定雛形を作成し、`--check-config` は設定を検査します。Windows の実行ファイル名は、アプリ名・Git ブランチ・ビルド元コミットから生成されます。上のコマンドには対象リリースの実際のファイル名を使用しています。

`TARGET_DIR` を相対パスで書いた場合は、`.env` ファイルがあるフォルダーからの相対パスとして解決されます。サーバー起動直後に `logs/latest.log` がまだ作られていなくても、ファイルが現れるまで待機します。

`.env` には Webhook URL が含まれるため、公開や共有をしないでください。リリース ZIP に含まれるのは `.env.example` のみです。

### 旧Python版の自動検出（v1.0.0-beta0 の次のビルド以降）

実行ファイルの横に `.env` があれば、その設定をそのまま使います。旧Python版のフォルダーに新しい実行ファイルを置く方法でも引き継げます。

実行ファイルの横に `.env` がない場合、作業フォルダーの旧Python版を優先して検出します。そこに見つからなければ、実行ファイルと同じフォルダー内、またはその親フォルダー内にある `Send-Minecraft-notifications` を確認します。旧版のソースと `.env` が残っているフォルダーが対象です。複数の候補が見つかった場合は自動選択せず、`--config <旧フォルダー>` または `--config <旧.envのパス>` で指定してください。別の場所にある旧版も同じ方法で指定できます。

読み込んだ旧 `.env` の場所は起動時に表示します。旧ファイルのコピーや上書きは行わず、新しく追加された未設定の項目には既定値を使います。明示した `--config` は自動検出より優先されます。`--init-config` を指定した場合は、自動検出せず新しい雛形を作成します。公開済みの `v1.0.0-beta0` では、上のコマンドのように旧 `.env` のファイルパスを指定してください。

## 通知とメッセージ設定

- ログのチャットを含め、通知から Discord のユーザー、ロール、`@everyone` へのメンションは行われません。
- `.env` のテンプレートで文字列として書いた `\n` は改行として送信されます。
- メッセージテンプレートなど、追加の設定項目は `.env.example` を参照してください。使わない任意項目は初期値のままにできます。

### ローマ字チャットの日本語表示（v1.0.0-beta1 の次のビルド以降）

`.env` に次を追加して再起動すると、Discordへ原文と日本語変換を併記します。既存の設定に追加しなければ無効のままです。

```dotenv
JAPANIZE_ENABLED=true
JAPANIZE_MODE=auto
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

```dotenv
JAPANIZE_DICTIONARY='{"maikura":"マイクラ","ohayou gozaimasu":"おはようございます"}'
```

日本語が含まれる発言、`/` または `$` で始まる発言は独自変換しません。URL、メール、メンション、コード、`minecraft:stone` のようなIDは変換対象から除外します。英単語とローマ字は厳密に判別できないため、変換が不要な発言には `$` を付けてください。原文と変換文の両方でDiscordメンションは禁止し、長文は上限内に分割します。

Minecraft Java版のバージョン番号やMod APIには依存せず、Vanilla/Fabricの通常ログ、Forge/NeoForgeのロガー付きログ、Paper/Spigotの非同期チャット、旧形式のINFOログを読みます。バージョン別の導入物は不要です。任意のプラグイン書式まで自動判別できるわけではなく、実機で全バージョンを起動検証したものではありません。チャット本文が `<Player> message` の形式ならスレッド名に依存せず認識します。`Player: message` はチャット用スレッドまたはLunaChatロガーと分かる行に限定して認識し、サーバーの診断表示と混同しません。スレッド情報のない独自書式では、サーバー側の公開チャット書式を `<%username> %msg` などにしてください。

LunaChatの既定の1行書式 `原文 (変換文)` と、Tsuki Chatの同一ログレコード内の `原文`＋改行＋`→ 変換文` に対応します。LunaChatでは `displayNormalChatOnConsole: true` と `japanizeDisplayLine: 1` にすると、原文と変換を同じ行から取得できます。別の本文書式には、次のように2つの項目を各1回含むテンプレートを指定できます。テンプレートは正規表現ではありません。

```dotenv
JAPANIZE_SERVER_FORMAT="{original} => [{japanese}]"
```

送信者のない別ログの `[JP] ...` や `→ ...` は、私信や別プレイヤーの変換の可能性があるため推測して結び付けません。その場合、`auto` は元の公開チャットから独自変換します。ゲーム内だけに表示されてログに残らない変換結果も取得できません。サーバー側プラグイン自身の外部通信設定は、このツールの設定とは別です。上流の書式は [LunaChatの設定](https://github.com/ucchyocean/LunaChat/blob/f8bf6e036354a0f04f23059ba6de8da6e9a9fca0/src/main/resources/config.yml) と [Tsuki Chatのログに渡す文字列](https://github.com/Meatwo310/tsuki-chat/blob/460f30b02b4b7a13fc9e396cd5f1adc8e295e8ec/1.20.1/forge/src/main/java/net/meatwo310/tsukichat/util/ChatCustomizer.java#L66) を参照してください。

チャンネル名から公開・非公開は判別できないため、名前付きチャンネルは既定では転送しません。公開と確認したチャンネルだけを明示します。私信の `[Player -> Target] ...` や、許可していない／識別できないチャンネル書式は除外します。

```dotenv
JAPANIZE_PUBLIC_CHANNELS=["global"]
```

### システム通知のアイコン

起動・終了、参加・退出、コンソールの発言、定期案内などのシステム・サーバー通知には、既定で自作の情報アイコン [info_icon_dot.png](assets/info_icon_dot.png) を使用します。特定プレイヤーのスキンを初期値には使用しません。画像はこのリポジトリの `main/assets/info_icon_dot.png` の固定Raw URLからDiscordが取得します。

管理者は `.env` で次のように変更できます。優先順位は `SENDER_ICON`、`SENDER_ICON_PLAYER`、既定の情報アイコンの順です。

| 設定 | 使用するアイコン |
| --- | --- |
| 両方空欄（または未設定） | 既定の情報アイコン |
| `SENDER_ICON="https://example.com/icon.png"` | 指定した画像URL |
| `SENDER_ICON=""` と `SENDER_ICON_PLAYER="PlayerName"` | 明示指定したMinecraftプレイヤーのアイコン（`PLAYER_ICON_API` を使用） |

既存の `.env` にプレイヤーのスキンURLが設定されている場合、既定の情報アイコンへ切り替えるには `SENDER_ICON` を空欄にしてください。プレイヤー本人のチャットには引き続きそのプレイヤーのアイコンを使用します。設定を変更した後は通知プログラムを再起動してください。

開発用の未公開ブランチでは、既定アイコンの画像を `main` に公開するまでRaw URLは利用できません。別の公開画像を使う場合は `SENDER_ICON` にそのURLを設定してください。

## 対応する配布ビルド

現在のリリースビルドは Windows x64 と Ubuntu 22.04 x64 で作成します。Linux x64 版は Ubuntu 22.04・24.04 で、Python を PATH に含めない環境での初回起動・設定検査を確認しています。Linux バイナリは glibc 2.35 以降を必要とします。ほかの OS、Linux ディストリビューション、CPU アーキテクチャでの互換性は保証していません。PyInstaller の one-file 実行ファイルは、起動時に内部ファイルを一時フォルダーへ展開します。

## 開発者向け

開発には Python 3.12 と [uv](https://docs.astral.sh/uv/) を使います。

実行前に `.env.example` を `.env` にコピーし、`WEBHOOK_URL` と `TARGET_DIR` を設定してください。

```sh
uv sync --frozen
uv run pytest
uv run python src/main.py
```

配布ビルドを作るときは、ビルドする OS 上で次を実行します。OS ごとのバイナリはそれぞれの OS 上でビルドしてください。

```sh
uv sync --frozen --group build
uv run python scripts/build_release.py
```

生成物は `dist/release/` に作成されます。単体バイナリ、バイナリと README・LICENSE・`.env.example` をまとめた ZIP、SHA-256 チェックサムが入ります。

## GitHub Actions による自動リリース

リリースタグを GitHub に push すると、Windows x64 と Linux x64 のビルドが自動で実行されます。`1.2.3`・`v1.2.3` のどちらの形式も使えます。このリポジトリではすべてのタグをリリースとして扱います。タグ名は英数字で始め、英数字と `.`, `_`, `/`, `+`, `-` を使用してください。タグの対象コミットに `.github/workflows/release.yml` が含まれている必要があります。

両 OS のテスト・単体実行チェックが成功した後、成果物のチェックサムを検証し、実行ファイル・ZIP・チェックサムの計6ファイルを同じ GitHub Release へ添付して自動公開します。リリースノートには変更履歴に加え、そのタグと実際の Windows ファイル名に合った Linux / PowerShell のダウンロード・設定・起動手順を日英で自動挿入します。配布 ZIP 内の README にも同じタグの手順を収録します。

公開後、既定ブランチの README の手順部分だけを GitHub Actions が更新します。最も新しく公開されたリリースを対象とし、古いリリースの再実行で URL を巻き戻しません。既定ブランチが直接更新を禁止している場合、この更新ステップは失敗するため、ブランチルールに応じた運用が必要です。手順の生成元は `scripts/release_docs.py` です。`smn:install-ja` / `smn:install-en` のコメントで囲んだ部分は自動生成されるので、文言を変更する場合は生成元を編集してください。

アップロード完了までは Draft 状態を維持し、途中で失敗した場合は公開しません。再実行では途中の Draft を完成させ、公開済みのリリースの添付ファイルは変更しません。README 更新が失敗しても、公開済みの実行ファイルは利用できます。

`1.2.3-rc.1`・`v1.2.3-beta.1` のようなタグは Prerelease として公開します。ベータタグでは Docker の `latest` タグを更新しません。追加のトークン設定は不要で、公開ジョブに限定した `GITHUB_TOKEN` の `contents: write` 権限を使用します。Actions からの手動実行はビルドと Actions artifact の作成のみで、リリースは公開しません。

## English

Download the Windows x64 `.exe` or Linux x64 binary from [Releases](https://github.com/AoSankaku/Send-Minecraft-notifications/releases). The standalone binary does not require Python, and you can run it without extracting a ZIP. On first run it creates a `.env` template beside itself. Set `WEBHOOK_URL` and `TARGET_DIR`, then run it again. Relative `TARGET_DIR` values are resolved from the folder containing `.env`. On Linux, run `chmod +x <binary>` first. The Linux build requires glibc 2.35 or newer. Other operating systems and architectures are not currently supported release targets.

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

### Japanese chat (builds after v1.0.0-beta1)

Add these settings to `.env` and restart to show original chat and Japanese text together. Missing settings default to disabled:

```dotenv
JAPANIZE_ENABLED=true
JAPANIZE_MODE=auto
```

`auto` reuses a Japanese result from the same public-chat record, otherwise converts locally. `local` always converts the original locally; `server` only uses recorded server results. Independent conversion is offline romaji-to-hiragana, without conversion APIs, model downloads, or dictionary services. It does not perform general kana-to-kanji conversion. Optional exact-word or whole-message dictionary entries can supply kanji and proper names:

```dotenv
JAPANIZE_DICTIONARY='{"maikura":"マイクラ","ohayou gozaimasu":"おはようございます"}'
JAPANIZE_SERVER_FORMAT=""
JAPANIZE_PUBLIC_CHANNELS=[]
```

Messages already containing Japanese or beginning with `/` or `$` skip local conversion. URLs, emails, mentions, code, and namespaced IDs remain intact. Romaji cannot always be distinguished from English; prefix a message with `$` to skip conversion. Mentions remain disabled in both lines, and long player messages are split within Discord's limit.

Common Vanilla/Fabric, Forge/NeoForge, Paper/Spigot async, and old INFO log layouts are supported without depending on a Minecraft version number or installing a version-specific mod. This is log-format compatibility, not a complete Minecraft runtime test matrix. Angle-style `<Player> message` works across these layouts. Colon-style `Player: message` requires a chat thread or LunaChat logger; for custom logs without that provenance, use an unambiguous public-chat server format such as `<%username> %msg`.

LunaChat's default single-line `original (Japanese)` and Tsuki Chat's same-record `original` followed by an unprefixed `→ Japanese` continuation are recognized. For LunaChat, enable normal console chat and single-line Japanize display. A custom `JAPANIZE_SERVER_FORMAT` must contain `{original}` and `{japanese}` once each, for example `{original} => [{japanese}]`; it is a literal template. Anonymous separate `[JP]` / arrow records may belong to private messages and are never guessed or forwarded. Results visible only in-game cannot be recovered from logs; `auto` falls back to local conversion. The server plugin's own network settings are independent of this tool.

Named channels are excluded by default because a name does not prove a channel is public. Only list channels you have verified are public, e.g. `JAPANIZE_PUBLIC_CHANNELS=["global"]`. Private-message and unrecognized channel layouts remain excluded.

### Additional configuration

Builds after `v1.0.0-beta0` automatically reuse an existing `.env` beside the executable. If none exists there, they check the working directory for a legacy Python checkout, then check folders named `Send-Minecraft-notifications` inside the executable's directory and its parent. The old source files and `.env` must still be present. If several neighboring checkouts are found, select one with `--config <old-directory>` or `--config <old-.env-path>`. Explicit `--config` takes priority. The selected legacy file's path is printed at startup; its contents are never copied or overwritten. Missing new settings use defaults. `--init-config` creates a new template instead of detecting old settings. For the published `v1.0.0-beta0`, pass the old `.env` file path as shown above.

System/server notifications use the original [info icon](assets/info_icon_dot.png) from this repository's fixed `main/assets/info_icon_dot.png` Raw URL by default; no player's skin is used as the default. Leave `SENDER_ICON` and `SENDER_ICON_PLAYER` empty or unset to use it. Administrators can set `SENDER_ICON` to a custom image URL, or leave it empty and set `SENDER_ICON_PLAYER` to a Minecraft player name to use that player's icon through `PLAYER_ICON_API`. An explicit image URL takes priority over a player name. Existing icon URLs remain supported; clear the old URL to switch to the default. Player chat continues to use each player's own icon. Restart the notifier after changing settings. The default image must be published to `main` before its Raw URL is available.

For development, install Python 3.12 and uv, copy `.env.example` to `.env`, and set `WEBHOOK_URL` and `TARGET_DIR`. Then run `uv sync --frozen`, `uv run pytest`, and `uv run python src/main.py`. To make a local release build, run `uv sync --frozen --group build` followed by `uv run python scripts/build_release.py` on the target operating system.

Pushing a release tag (for example `1.2.3` or `v1.2.3`) runs both platform builds and publishes one GitHub Release containing both binaries, ZIPs, and checksums after tests and asset verification succeed. Tag names must start with an ASCII letter or digit and contain only ASCII letters, digits, `.`, `_`, `/`, `+`, or `-`. The tagged commit must include the release workflow. Each ZIP's README and the release notes include generated Linux and PowerShell installation commands using that release's tag and actual Windows filename. After publication, Actions updates only the managed installation sections of the default branch's README. Older release reruns cannot roll the URLs back. Branch rules must allow this README update; if it fails, the published binaries remain available. Edit `scripts/release_docs.py` to change instructions inside the `smn:install-ja` / `smn:install-en` markers.

Version tags with a suffix such as `-rc.1` publish a prerelease and do not update Docker's `latest` tag. Failed uploads remain drafts; reruns complete drafts while preserving published releases. Manual workflow runs create Actions artifacts only. No additional token is required.

## License

MIT. See [LICENSE](LICENSE).
