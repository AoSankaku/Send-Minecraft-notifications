import os, re, time, requests, copy

from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver

# ここにDiscordのWebhookのURLを貼り付けてください。
# Enter your discord (or other services) webhook URL here!
webhook_url = "https://paste.your.webhook.address/here"
target_dir = "./logs/"
target_file = "latest.log"

prev = []
# status = "init" or "online" or "closing"
# この数値は好きに利用してください
# You can use this variable if you need 
status = "init"

# プラグイン名を取得
# Fetching names of plugins
plugin_names = os.listdir("./plugins")

# カンマ区切りで「名前としてみなさない」文字列を入れてください
# Insert strings which you don't want to be recognized as a player's name, separating with comma
plugin_names.extend(["ChunkTaskScheduler", "ChunkHolderManager"])

def SendMessage(message: str) -> None:
    # discord以外のサービスのwebhookの場合はここを変更してください
    # If you wish to use services other than discord, customize here based on your service:
    main_content = {"content": message}
    requests.post(webhook_url, main_content)

def MessageCreation(text: str):
    global status, plugin_names
    print(text)
    # 参加メッセージ
    # When someone joined
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Server thread/INFO]: (.*) joined the game", text)
    if len(match) :
        return ":green_circle: " + str(match[0]) + " が参加しました。一緒に遊んであげよう！"
    # 退出メッセージ
    # When someone left
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Server thread/INFO]: (.*) left the game", text)
    if len(match) :
        return ":red_circle: " + str(match[0]) + " が退出しました。"
    # サーバー起動メッセージ
    # When your server is launched
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Server thread/INFO]: Done ", text)
    if len(match) :
        status = "online"
        return ":door: **【サーバーがオンラインになりました！】** :door:"
    # サーバー終了メッセージ
    # When your server is closed
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Server thread/INFO]: Closing Server", text)
    if len(match) :
        status = "closing"
        return ":no_entry_sign: **【サーバーがオフラインになりました。】** :no_entry_sign:"
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
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Server thread/INFO]: \[Not Secure] \[(.*)](.*)", text)
    if len(match) and not(str(match[0][0]) in plugin_names) and status == "online" :
        print(str(match))
        return f'`[{str(match[0][0])}]{str(match[0][1])}`'
    # セキュアなsayコマンド経由のチャット
    # non-secure chat sent by "say" command
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Server thread/INFO]: \[(.*)](.*)", text)
    if len(match) and not(str(match[0][0]) in plugin_names) and status == "online" :
        print(str(match))
        return f'`[{str(match[0][0])}]{str(match[0][1])}`'
    
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
