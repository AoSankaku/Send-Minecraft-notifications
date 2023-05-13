# Send-Minecraft-notifications（日本語説明）
これは他プロジェクトのフォークです。

## これは何？
Minecraftのサーバーで、

- サーバーの起動と閉鎖
- プレイヤーの入退室
- サーバーにいるプレイヤーのチャット

などを、Webhook経由でDiscordに送信するPythonスクリプトです。
Minecraftのサーバーのログの差分を取得し、それを元にWebHookリクエストを送信することでDiscordに通知を送ります。

例えばサーバーの起動と閉鎖、誰かがログイン/ログアウトした情報などのほか、ログを直接参照しているため、ログに書いてあることはすべて扱うことができます。

オリジナルの作者はLinuxの動作を確認しています。私はWindowsでも正常に動くようにプロジェクトを改変しましたが、オリジナルのものでもエラーなく動作します。

## 変更点
このリポジトリのmain.pyはオリジナルのものに対して中規模の修正をしています。
- 「最後のログを取得してログを作る」というコードになっていたため、一瞬で2～3行更新されたときなどに正常に動かなくなるバグを構造変更により修正しました。具体的には「現在のログと前回取得時のログの差分を比較する」という方式を採用しました。そのため、このスクリプトはログが入るフォルダに新しくファイルを自動的に生成します。
- 英語の補足を複数付け足しました。
- デフォルトで「サーバーの起動/閉鎖」「サーバープレイヤーのチャット」を流すようにしました。おそらくGeyserMCのPrefixなどがついていても正常に動作するはずです。
- チャットでシステムログの偽装ができなくなるように、正規表現を改変しました。例えば、誰かがいたずらでチャットに「tesutodesuyo:Darekasan left the game.」と入力してもログアウトとして扱わなくなりました。
- Discordの絵文字に対応しました。
- いくつかのスペルミスと変数命名規則を修正しました。
- README.mdを大幅に書き換えました。

## 使い方
### 事前準備
以下のものが必要です。特にWindowsユーザーの場合は最初から入っているわけではないため、すべてインストールしてください。

#### Python 3
このプログラムはPythonで動くため、Pythonのインストールが必要です。
Microsoft Storeからも入ると思いますので適当に最新版をインストールしてください。

#### Watchdog(Pythonライブラリ)
「Windowsキー」を押しながら「R」を押すと出てくる画面に```cmd```と入れてEnterを押してください。

その後出てきた黒い画面に、

```cmd
pip install watchdog
```

と入力してください。実行場所はどこでも構いません。

以下はオプションです。

#### Git
githubに普段からお世話になっている人は、gitを入れておくと幸せになれるかもしれません。[入れておきましょう。](https://git-scm.com)

このプロジェクトもgitがあれば簡単に複製できます。

### 導入方法
#### 1-A. Gitを利用する場合
「Windowsキー」を押しながら「R」を押すと出てくる画面に```cmd```と入れてEnterを押してください。

その後出てきた黒い画面に、
```cmd
cd <マイクラサーバーのフォルダ>
```
と入れてEnterを押し、実行してください。マイクラサーバーのフォルダはエクスプローラーのアドレスバーからコピーしてください。コマンドはこんなのになるはずです。
```
cd C:\Users\anatanoyu-za-mei\path\to\your\server
```
これでディレクトリの移動が完了しました。このまま続けて、
```cmd
git clone https://github.com/AoSankaku/Send-Minecraft-notifications.git
```
と入力してください。フォルダの中に「Send-Minecraft-notifications」という名前のフォルダとその中に「main.py」が入っていれば成功です。

#### 1-B. Gitを利用しない場合
1. マイクラサーバーと同じフォルダに「Send-Minecraft-notifications」という名前のフォルダを作ってください。
1. その後、[このリポジトリのmain.py](https://github.com/AoSankaku/Send-Minecraft-notifications/blob/main/main.py)を開き、ダウンロードっぽいボタンを押してください。ダウンロード方法がどうしても分からなければ、「main.py」を先程のフォルダの中に作成し、中身をコピペしてください。
1. ダウンロードしたmain.pyを先程作ったフォルダに移動してください。これで完了です。

#### 2. batの準備
##### マイクラサーバー立ち上げ時に同時に起動したい場合
マイクラサーバーのあるフォルダでサーバー起動用のbatファイルがある人は、batファイルを以下のように書き換えてください。
```bat
start python ./Send-Minecraft-notifications/main.py
(次の行に元々あった「java」で始まるサーバー起動コード)
```
##### マイクラサーバー立ち上げとは別に起動したい場合
以下の内容のbatファイルを作成してください。
```bat
python ./Send-Minecraft-notifications/main.py
```
サーバー開放通知を正しく送信するために、サーバー起動前にこちらを先に起動しておくことを推奨します。

#### 3.終了処理
開いた黒いウィンドウを閉じれば動作は終了します。サーバーが終了したときも自動で終了するようになっているはずです。

## 注意点
- DiscordのWebhookを使用する場合、Discord側のチャットを読み出すことは**DiscordのWebhookの仕様上不可能**です。対話型にしたい場合はBOTの作成と運用が必要です（このスクリプトは部分的に利用できるかもしれませんが、基本的に使用不可と思ってください。）。
- このスクリプトは`latest.log`の内容を元に`latest.log.prev`を高速で生成し、書き換えを行います。HDDなど読み書き速度の遅い記憶媒体を使用していると悪影響があるかもしれません。
- このスクリプトは`latest.log`と同じディレクトリに`latest.log.prev`を自動的に作成しますが、以下のことはしないでください。
  - スクリプトおよびサーバー動作中の削除（いずれかを完全に停止させたあとなら改変しても大丈夫です）
  - `latest.log`または`latest.log.prev`の文字コード変更（挙動が崩壊します！絶対にやらないでください。やってしまった場合は`latest.log.prev`をまるごと削除してください。削除するまで正常に動作しなくなります。）

## バグを見つけたら
[このリポジトリのIssue](https://github.com/AoSankaku/Send-Minecraft-notifications/issues)を開いてください。開き方がわからない人はググってください。

Pythonのエラーコードが出ている場合、可能であればそのエラーコードを個人情報に気をつけて貼り付けるようにしてください。

***

# Send-Minecraft-notifications (Instructions in English)

## About
You can get a notification in your discord server using WebHook everytime the server log file is changed.
This creates a notification when your server starts/shuts down, when someone logs in or out, or for any event in your log file.

## Usage

### Preparation
You'll need all there followings:
#### Python 3
Since this script is written in Python, you will need an appropriate version of Python.

Just install from Microsoft Store, or the official website.

#### Git
If you visit github.com often, it is better choice to [install git]((https://git-scm.com)).

You can use Git to download our files easily.

### Installation
#### 1-A. If you're using Git
Press the Windows and R keys to open an execution window, then enter:
```bat
cd <Enter your minecraft server directory here>
```
Your input will be look like this:
```bat
cd C:\path\to\your\minecraft\server\folder
```

and next, execute:
```bat
git clone https://github.com/AoSankaku/Send-Minecraft-notifications.git
```

After doing this, confirm that "Send-Minecraft-notifications" folder exists in your server folder.

#### 1-B. If you're not using Git
1. Create a folder named "Send-Minecraft-notifications"
2. [Open main.py in our repository](https://github.com/AoSankaku/Send-Minecraft-notifications/blob/main/main.py) then download it manually, or create a file named "main.py" in "Send-Minecraft-notifications" and copy the code and paste it to your file, then save.
3. Put main.py in "Send-Minecraft-notifications"

#### 2. Prepare your .bat file
##### Start this script when you start the server
Above your existing line which launches your minecraft server, add:
```bat
start python ./Send-Minecraft-notifications/main.py
```

##### Start this script manually
Create a .bat file and then paste:
```bat
python ./Send-Minecraft-notifications/main.py
```
Start this script before launching server to get notified when the server is open.

##### Stopping script
Just close the black window.

## Warning
- This script **CAN'T PULL MESSAGES ON DISCORD**. If you wish to do this, you have to create and run a discord bot.
- This script generates `latest.log.prev` every time the log file is changed. Slow storage such as HDD may affect your computer's performance.
- This script generates `latest.log.prev` based on `latest.log`. Please DON'T do them:
  - Deleting `latest.log.prev` when the script is running (After stopping this script, you can delete this)
  - Changing the encoding method of `latest.log.prev` (Be careful if you are using any language other than English)

## I found a bug!
[Open an issue on this repository](https://github.com/AoSankaku/Send-Minecraft-notifications/issues). If you do not know how to open an issue, please Google it.

If you are encountering an issue with a Python error code, include the information in your issue.
