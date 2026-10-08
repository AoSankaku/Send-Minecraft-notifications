# Send-Minecraft-notifications

Minecraft サーバーのログを監視し、起動・終了、プレイヤーの参加・退出、チャットなどを Discord の Webhook に通知します。Discord からのメッセージ取得や返信は行いません。

## すぐに使う（Python 不要）

1. [Releases](https://github.com/AoSankaku/Send-Minecraft-notifications/releases) から実行ファイルをダウンロードします。Windows x64 は `.exe`、Linux x64 は拡張子のない実行ファイルです。単体ファイルを使う場合、ZIP の展開は不要です。
2. 実行ファイルを任意のフォルダーに置いて起動します。初回起動時に同じフォルダーへ `.env` の雛形が作られます。
3. `.env` の `WEBHOOK_URL` に Discord Webhook URL を、`TARGET_DIR` に Minecraft サーバーのログフォルダーを設定します。
4. 実行ファイルを再起動します。

Linux では実行権限を付けてから起動してください。

```sh
chmod +x ./send-minecraft-notifications-linux-x64
./send-minecraft-notifications-linux-x64
```

必要に応じて設定ファイルの場所を `--config <path>` で指定できます。`--init-config` は設定雛形を作成し、`--check-config` は設定を検査します。たとえば、Windows では次のように実行します。

```powershell
.\send-minecraft-notifications-windows-x64.exe --init-config
.\send-minecraft-notifications-windows-x64.exe --config .\.env --check-config
```

`TARGET_DIR` を相対パスで書いた場合は、`.env` ファイルがあるフォルダーからの相対パスとして解決されます。サーバー起動直後に `logs/latest.log` がまだ作られていなくても、ファイルが現れるまで待機します。

`.env` には Webhook URL が含まれるため、公開や共有をしないでください。リリース ZIP に含まれるのは `.env.example` のみです。

## 通知とメッセージ設定

- ログのチャットを含め、通知から Discord のユーザー、ロール、`@everyone` へのメンションは行われません。
- `.env` のテンプレートで文字列として書いた `\n` は改行として送信されます。
- メッセージテンプレートなど、追加の設定項目は `.env.example` を参照してください。使わない任意項目は初期値のままにできます。

## 対応する配布ビルド

現在のリリースビルドは Windows x64 と Ubuntu 22.04 x64 で作成します。Linux バイナリは glibc 2.35 以降を必要とします。ほかの OS、Linux ディストリビューション、CPU アーキテクチャでの互換性は保証していません。PyInstaller の one-file 実行ファイルは、起動時に内部ファイルを一時フォルダーへ展開します。

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

生成物は `dist/release/` に作成されます。単体バイナリ、バイナリと README・LICENSE・`.env.example` をまとめた ZIP、SHA-256 チェックサムが入ります。`v*` タグを push すると Windows と Linux のビルド後に両方のアセットを含む Draft GitHub Release が作られます。管理者が内容を確認して公開してください。Actions から手動実行した場合は Actions artifact のみを作成します。

## English

Download the Windows x64 `.exe` or Linux x64 binary from [Releases](https://github.com/AoSankaku/Send-Minecraft-notifications/releases). The standalone binary does not require Python, and you can run it without extracting a ZIP. On first run it creates a `.env` template beside itself. Set `WEBHOOK_URL` and `TARGET_DIR`, then run it again. Relative `TARGET_DIR` values are resolved from the folder containing `.env`. On Linux, run `chmod +x <binary>` first. The Linux build requires glibc 2.35 or newer. Other operating systems and architectures are not currently supported release targets.

For development, install Python 3.12 and uv, copy `.env.example` to `.env`, and set `WEBHOOK_URL` and `TARGET_DIR`. Then run `uv sync --frozen`, `uv run pytest`, and `uv run python src/main.py`. To make a local release build, run `uv sync --frozen --group build` followed by `uv run python scripts/build_release.py` on the target operating system.

## License

MIT. See [LICENSE](LICENSE).
