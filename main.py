import os, re, time, requests, copy

from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver

# ここにDiscordのWebhookのURLを貼り付けてください。
# Enter your discord (or other services) webhook URL here!
webhook_url = "https://paste.your.webhook.address/here"
target_dir = "./logs/"
target_file = "latest.log"

prev = []
player_count = 0
chat_count = 0
# status = "init" or "online" or "closing"
# この数値は好きに利用してください
# You can read this variable if you need 
status = "init"

# プラグイン名を取得
# Fetching names of plugins
plugin_names = os.listdir("./plugins")

# カンマ区切りで「名前としてみなさない」文字列を入れてください
# Insert strings which you don't want to be recognized as a player's name, separating with comma
plugin_names.extend(["ChunkTaskScheduler", "ChunkHolderManager", "BE"])

# 拡張子、大文字小文字を無視
raw_plugin_names = copy.deepcopy(plugin_names)

for i, a in enumerate(raw_plugin_names):
    plugin_names.append(os.path.splitext(a)[0].casefold())
    plugin_names[i] = re.sub("[\_\-]([0-9]{1,}\.)+[0-9]{1,}", "", plugin_names[i])


def SendMessage(message: str) -> None:
    global chat_count, player_count
    # discord以外のサービスのwebhookの場合はここを変更してください
    # If you wish to use services other than discord, customize here based on your service:
    main_content = {"content": message}
    requests.post(webhook_url, main_content)
    chat_count += 1

    # メッセージ定義
    player_count_notify_message = {"content": f':information_source: 現在サーバーにいるプレイヤーは {player_count} 人です。みんな待ってるよ:eyes:'}
    # 20回ログを流したら人数を自動送信
    if (chat_count > 20):
        chat_count = 0
        requests.post(webhook_url, player_count_notify_message)

def MessageCreation(text: str):
    global status, plugin_names, player_count, chat_count
    print(text)
    # 参加メッセージ
    # When someone joined
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Server thread/INFO]: (.*) joined the game", text)
    if len(match) :
        player_count += 1
        chat_count = 0
        return f":green_circle: {str(match[0])} が参加しました。一緒に遊んであげよう！（現在 {player_count} 名）"
    # 退出メッセージ
    # When someone left
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Server thread/INFO]: (.*) left the game", text)
    if len(match) :
        player_count -= 1
        chat_count = 0
        return f":red_circle: {str(match[0])} が退出しました。（現在 {player_count} 名）"
    # サーバー起動メッセージ
    # When your server is launched
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Server thread/INFO]: Done ", text)
    if len(match) :
        status = "online"
        return "==================================================\n:door: **【サーバーがオンラインになりました！】** :door:\n=================================================="
    # サーバー終了メッセージ
    # When your server is closed
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Server thread/INFO]: Closing Server", text)
    if len(match) :
        status = "closing"
        return "==================================================\n:no_entry_sign: **【サーバーがオフラインになりました。】** :no_entry_sign:\n=================================================="
    # その他好きに追加・削除可能（上にあるものもいらないやつは消してOK）
    # You can freely add or remove some messages above or below

    # セキュアなチャット
    # secure chat
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Async Chat Thread - #(.*)/INFO]: <(.*)>(.*)", text)
    if len(match) :
        return f'`[{str(match[0][1])}]{str(match[0][2])}`'
    # セキュアではないチャット
    # non-secure chat
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Async Chat Thread - #(.*)/INFO]: \[(.*)] <(.*)>(.*)", text)
    if len(match) :
        print(str(match))
        return f'`[{str(match[0][2])}]{str(match[0][3])}`'

    # セキュアではないsayコマンド経由のチャット
    # non-secure chat sent by "say" command
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Server thread/INFO]: \[Not Secure] \[(.*?)] (.*)", text)
    if len(match) and not(str(match[0][0]).casefold() in plugin_names) and status == "online" :
        print(str(match))
        return f'`[{str(match[0][0])}] {str(match[0][1])}`'
    # セキュアなsayコマンド経由のチャット
    # secure chat sent by "say" command
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Server thread/INFO]: \[(.*?)] (.*)", text)
    if len(match) and not(str(match[0][0]).casefold() in plugin_names) and status == "online" :
        print(str(match))
        return f'`[{str(match[0][0])}] {str(match[0][1])}`'
    
    # セキュアではないLunachat対応コマンド
    # non-secure Luna chat(You don't need this unless someone uses Japanese in your server)
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Async Chat Thread - #(.*)/INFO]: \[Not Secure] (.*): (.*)", text)
    if len(match) :
        return f'`[{str(match[0][1])}] {str(match[0][2])}`'
    
    # セキュアなLunachat対応コマンド
    # secure Luna chat(You don't need this unless someone uses Japanese in your server)
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Async Chat Thread - #(.*)/INFO]: (.*): (.*)", text)
    if len(match) :
        return f'`[{str(match[0][1])}] {str(match[0][2])}`'
    
    # ホワイトリストに入ってない時の通知
    # join attempt from non-whitelisted player
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Server thread/INFO]: Disconnecting (.*?name=)(.*?),(.*?You are not whitelisted on this server!)", text)
    if len(match) :
        return f':yellow_circle: {str(match[0][1])} がサーバーに入ろうとしましたが、ホワイトリストに入っていません！'
    
    # プレイヤー数再計算
    # recalculate player count
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Server thread/INFO]: There are ([0-9]*) of a max of ([0-9]*) players online:", text)
    if len(match) :
        player_count = int(match[0][0])
        chat_count = 0
        return f':information_source: 現在サーバーにいるプレイヤーは {player_count} 人です。（上限 {str(match[0][1])} 名）'
    
    # 実績通知
    # advancements
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Server thread/INFO]: (.*) has made the advancement \[(.*)]", text)
    if len(match) :
        return f':trophy: {str(match[0][0])} が進捗[{str(match[0][1])}]を達成しました！'
    
    # 挑戦通知
    # challenges
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Server thread/INFO]: (.*) has completed the challenge \[(.*)]", text)
    if len(match) :
        return f':military_medal: {str(match[0][0])} が挑戦[{str(match[0][1])}]を達成しました！'
    
    return None


def GetLog(filepath: str):

    global prev, status

     # 先に現在のログを取得（こっちを先にしないとずれる）
    with open(filepath, "r", errors="ignore") as f:
        log = f.readlines()
        # 前回のログを参照する
        oldLog = copy.deepcopy(prev)
        # oldLogに古いログが入っているのでprevを更新
        prev = copy.deepcopy(log)

    # どうやらサーバーをつけたまま日付をまたぐとlatest.logがまるっきり書き換わるらしいのでそれに対応できるように
    # 理論上、logはoldlogの中身を完全に包括しているはずなので、そうでない場合は「まるごと置き換わった」とみなす
    # oldLogとlogの時刻、長さを比べる方法やosの時間を比較する方法も浮かんだが、不具合を生む可能性が高いと判断した
    # 極稀に(log AND oldLog)に重複が生まれる可能性あり、将来的に対処が必要
    joinedLog = '\n'.join(log)
    joinedOldLog = '\n'.join(oldLog)
    if (
        # 判定条件：logがoldLogで始まらない（logはoldLogの延長でないと矛盾が生じる）＝日付をまたいだ
        # 「この配列で始まる」は原理的に不可能なので、文字列に変換して判定
        not(joinedLog.startswith(joinedOldLog))
    ):
        # いずれかに当てはまる場合はoldLogはなかったものとして削除する
        # こうすることでoldLogの長さは0になり、常にlogを読むようになる
        oldLog = []


    # oldLogとlogの排他的論理和だと「連続で同じ文字を送信した」などの特殊な状況の場合に反応しなくなるため
    # 「len(oldLog)-1の長さだけlogの要素を削除する」で決着
    del log[:len(oldLog)]
    diff = log
    print(len(log))
    print(len(oldLog))

    # 送信メッセージ作成
    for e in diff:
        text = MessageCreation(e)
        if text is not None:
            SendMessage(text)

    # サーバーの終了を検知したらスクリプト停止
    if(status == "closing"):
        print("server closing detected!!")
        os._exit(-1)


class ChangeHandler(FileSystemEventHandler):
    # フォルダ変更時のイベント
    def on_modified(self, event):
        filepath = event.src_path

        # ファイルでない場合無視する
        if os.path.isfile(filepath) is False:
            return

        # 監視対応のファイルでない場合無視する
        filename = os.path.basename(filepath)
        if filename != target_file:
            return

        GetLog(filepath)
        
if __name__ in "__main__":
    while 1:
        event_handler = ChangeHandler()
        observer = PollingObserver()
        observer.schedule(event_handler, target_dir, recursive=True)
        observer.start()
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
