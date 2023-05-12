# Send-Minecraft-notifications
## これは何？
Minecraftのサーバーのログの差分を取得し、それを元にWebHookリクエストを送信することでDiscordに通知を送ります。
例えばサーバーの起動と閉鎖、誰かがログイン/ログアウトした情報などのほか、ログを直接参照しているため、ログに書いてあることはすべて扱うことができます。

## What is this?
You can get a notification in your discord server using WebHook everytime the server log file is changed.
This creates a notification on starting/shutting down your server, someone logging in or out, or every event on your log file.

## 使い方
.batファイルを作り、
```bat
python ./Send-Minecraft-notifications/main.py
```
と入力すればOKです。