import os, re, time, difflib, shutil, requests

from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver

# ここにDiscordのWebhookのURLを貼り付けてください。
# Enter your discord (or other services) webhook URL here!
webhook_url = "https://paste.your.webhook.address/here!"
target_dir = "./logs/"
target_file = "latest.log"

def SendMessage(message: str) -> None:
    # discord以外のサービスのwebhookの場合はここを変更してください
    # If you wish to use services other than discord, customize here based on your service:
    main_content = {"content": message}
    requests.post(webhook_url, main_content)

    # サーバー閉鎖を感知したら停止
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Server thread/INFO]: Closing Server", message)
    if len(match) == 1:
        exit()

def MessageCreation(text: str):
    print(text)
    # 参加メッセージ
    # When someone joined
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Server thread/INFO]: (.*) joined the game", text)
    if len(match) == 1:
        return ":green_circle: " + str(match[0]) + " が参加しました。一緒に遊んであげよう！"
    # 退出メッセージ
    # When someone left
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Server thread/INFO]: (.*) left the game", text)
    if len(match) == 1:
        return ":red_circle: " + str(match[0]) + " が退出しました。"
    # サーバー起動メッセージ
    # When your server is launched
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Server thread/INFO]: Done ", text)
    if len(match) == 1:
        return ":door: **【サーバーがオンラインになりました！】** :door:"
    # サーバー終了メッセージ
    # When your server is closed
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Server thread/INFO]: Closing Server", text)
    if len(match) == 1:
        return ":no_entry_sign: **【サーバーがオフラインになりました。】** :no_entry_sign:"
    # その他好きに追加・削除可能（上にあるものもいらないやつは消してOK）
    # You can freely add or remove some messages above or below

    # セキュアなチャット
    # secure chat
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Async Chat Thread - #(.*)/INFO]: <(.*)>(.*)", text)
    if len(match) == 1:
        return f'`[{str(match[0][1])}]{str(match[0][2])}`'
    # セキュアではないチャット
    # non-secure chat
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Async Chat Thread - #(.*)/INFO]: \[(.*)] <(.*)>(.*)", text)
    if len(match) == 1:
        print(str(match))
        return f'`[{str(match[0][2])}]{str(match[0][3])}`'
    
    return None


def GetLog(filepath: str):

     # 先に現在のログを取得（こっちを先にしないとずれる）
    with open(filepath, "r", encoding="cp932", errors="ignore") as f:
        log = f.readlines()
    
    # 前回のログを参照する（.prevファイルが存在しない場合は何も実行しない）
    try:
        oldLogRaw = open(f'{target_dir}{target_file}.prev', "r", encoding="cp932", errors="ignore")
        oldLog = oldLogRaw.readlines()
        oldLogRaw.close()
    except FileNotFoundError:
        oldLog = [""]

    # 読み込みが終わった段階でdiff作成
    CreateDiff()
   
    # latest.logの配列数がlatest.log.prevの配列数より少ない＝新規作成ファイルなのでprevの内容は無視する
    if (len(log) < len(oldLog)):
         oldLog = [""]

    # oldLogとlogの排他的論理和を取って、一致しない部分だけを文字列としてそれぞれ送信する
    # diff = set(oldLog) ^ set(log)
    #
    # 排他的論理和だと「連続で同じ文字を送信した」などの特殊な状況の場合に反応しなくなるため
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


def CreateDiff():
    # 処理終了時にその時点のlatest.logをlatest.log.prevとして保存して次回比較に使用する
    shutil.copyfile(f'{target_dir}{target_file}', f'{target_dir}{target_file}.prev')

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
