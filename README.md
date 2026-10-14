# Send-Minecraft-notifications

Minecraft サーバーのログを監視し、起動・終了、プレイヤーの参加・退出、チャットなどを Discord の Webhook に通知します。Discord からのメッセージ取得や返信は行いません。

## すぐに使う（Python 不要）

1. [Releases](https://github.com/AoSankaku/Send-Minecraft-notifications/releases) から実行ファイルをダウンロードします。Windows x64 は `.exe`、Linux x64 は拡張子のない実行ファイルです。単体ファイルを使う場合、ZIP の展開は不要です。
2. 実行ファイルを任意のフォルダーに置いて起動します。初回起動時に同じフォルダーへ `.env` の雛形が作られます。
3. `.env` の `WEBHOOK_URL` に Discord Webhook URL を、`TARGET_DIR` に Minecraft サーバーのログフォルダーを設定します。
4. 実行ファイルを再起動します。

Ubuntu Server では Linux x64 版をダウンロードし、設定を書き込めるフォルダーに置いてください。Python のインストールは不要です。実行権限を付けて起動すると `.env` が作られます。

```sh
chmod +x ./send-minecraft-notifications-linux-x64
./send-minecraft-notifications-linux-x64
```

`.env` の `WEBHOOK_URL` と `TARGET_DIR` を編集した後、設定を検査して起動します。`TARGET_DIR` には実際のサーバーのログフォルダーを指定してください。

```sh
./send-minecraft-notifications-linux-x64 --check-config
./send-minecraft-notifications-linux-x64
```

単体ファイルとチェックサムをダウンロードした場合は、実行前に次のコマンドで整合性を確認できます。ZIP をダウンロードしていなくても検査できます。

```sh
sha256sum --check --ignore-missing SHA256SUMS-linux-x64.txt
```

必要に応じて設定ファイルの場所を `--config <path>` で指定できます。`--init-config` は設定雛形を作成し、`--check-config` は設定を検査します。たとえば、Windows では次のように実行します。

Windows の実行ファイル名は、アプリ名・Git ブランチ・ビルド元コミットから生成されます。以下の `smn-main-abcdef0.exe` はファイル名の例です。ダウンロードした実際のファイル名に置き換えてください。

```powershell
.\smn-main-abcdef0.exe --init-config
.\smn-main-abcdef0.exe --config .\.env --check-config
```

`TARGET_DIR` を相対パスで書いた場合は、`.env` ファイルがあるフォルダーからの相対パスとして解決されます。サーバー起動直後に `logs/latest.log` がまだ作られていなくても、ファイルが現れるまで待機します。

`.env` には Webhook URL が含まれるため、公開や共有をしないでください。リリース ZIP に含まれるのは `.env.example` のみです。

## 通知とメッセージ設定

- ログのチャットを含め、通知から Discord のユーザー、ロール、`@everyone` へのメンションは行われません。
- `.env` のテンプレートで文字列として書いた `\n` は改行として送信されます。
- メッセージテンプレートなど、追加の設定項目は `.env.example` を参照してください。使わない任意項目は初期値のままにできます。

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

リリースタグを GitHub に push すると、Windows x64 と Linux x64 のビルドが自動で実行されます。`1.2.3`・`v1.2.3` のどちらの形式も使えます。このリポジトリではすべてのタグをリリースとして扱います。タグの対象コミットに `.github/workflows/release.yml` が含まれている必要があります。

両 OS のテスト・単体実行チェックが成功した後、成果物のチェックサムを検証し、実行ファイル・ZIP・チェックサムの計6ファイルを同じ GitHub Release へ添付して自動公開します。リリースノートも自動生成されます。アップロード完了までは Draft 状態を維持し、途中で失敗した場合は公開しません。再実行では途中の Draft を完成させ、公開済みのリリースの添付ファイルは変更しません。

`1.2.3-rc.1`・`v1.2.3-beta.1` のようなタグは Prerelease として公開します。ベータタグでは Docker の `latest` タグを更新しません。追加のトークン設定は不要で、公開ジョブに限定した `GITHUB_TOKEN` の `contents: write` 権限を使用します。Actions からの手動実行はビルドと Actions artifact の作成のみで、リリースは公開しません。

## English

Download the Windows x64 `.exe` or Linux x64 binary from [Releases](https://github.com/AoSankaku/Send-Minecraft-notifications/releases). The standalone binary does not require Python, and you can run it without extracting a ZIP. On first run it creates a `.env` template beside itself. Set `WEBHOOK_URL` and `TARGET_DIR`, then run it again. Relative `TARGET_DIR` values are resolved from the folder containing `.env`. On Linux, run `chmod +x <binary>` first. The Linux build requires glibc 2.35 or newer. Other operating systems and architectures are not currently supported release targets.

The Linux x64 binary has passed first-run setup and configuration smoke checks on Ubuntu 22.04 and 24.04 with Python removed from PATH. On Ubuntu Server, put it in a writable directory, run it once to create `.env`, edit `WEBHOOK_URL` and `TARGET_DIR`, then run `./send-minecraft-notifications-linux-x64 --check-config` before starting it again.

System/server notifications use the original [info icon](assets/info_icon_dot.png) from this repository's fixed `main/assets/info_icon_dot.png` Raw URL by default; no player's skin is used as the default. Leave `SENDER_ICON` and `SENDER_ICON_PLAYER` empty or unset to use it. Administrators can set `SENDER_ICON` to a custom image URL, or leave it empty and set `SENDER_ICON_PLAYER` to a Minecraft player name to use that player's icon through `PLAYER_ICON_API`. An explicit image URL takes priority over a player name. Existing icon URLs remain supported; clear the old URL to switch to the default. Player chat continues to use each player's own icon. Restart the notifier after changing settings. The default image must be published to `main` before its Raw URL is available.

For development, install Python 3.12 and uv, copy `.env.example` to `.env`, and set `WEBHOOK_URL` and `TARGET_DIR`. Then run `uv sync --frozen`, `uv run pytest`, and `uv run python src/main.py`. To make a local release build, run `uv sync --frozen --group build` followed by `uv run python scripts/build_release.py` on the target operating system.

Pushing any release tag (for example `1.2.3` or `v1.2.3`) runs both platform builds and publishes one GitHub Release containing both binaries, ZIPs, and checksums after tests and asset verification succeed. The tagged commit must include the release workflow. Version tags with a suffix such as `-rc.1` publish a prerelease and do not update Docker's `latest` tag. Failed uploads remain drafts; reruns complete drafts while preserving published releases. Manual workflow runs create Actions artifacts only. No additional token is required.

## License

MIT. See [LICENSE](LICENSE).
