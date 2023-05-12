import os, re, time, difflib, shutil, requests

from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver

webhook_url = "enter your discord webhook url here"
target_dir = "./logs/"
target_file = "latest.log"


def SendMessage(message: str) -> None:
    # discode以外のサービスのwebhookの場合はここを変更してください
    main_content = {"content": message}
    requests.post(webhook_url, main_content)

def MessageCreation(text: str):
    print(text)
    # 参加,退出以外のメッセージが必要な場合はここに書く
    match = re.findall(": (.*) joined the game", text)
    if len(match) == 1:
        return ":green_circle: " + str(match[0]) + " が参加しました。一緒に遊んであげよう！"
    match = re.findall(": (.*) left the game", text)
    if len(match) == 1:
        return ":red_circle: " + str(match[0]) + " が退出しました。"
    match = re.findall(": (.*) For help, type \"help\"", text)
    if len(match) == 1:
        return ":door: **サーバーがオンラインになりました！**"
    match = re.findall(": (.*) Closing Server", text)
    if len(match) == 1:
        return ":no_entry_sign: **サーバーがオフラインになりました。**"

    return None


def GetLog(filepath: str):
    # 最終行のテキストを取得
    with open(filepath, "r") as f:
        endtxt = f.readlines()[-1]

    # 送信メッセージ作成
    text = MessageCreation(endtxt)

    if text is not None:
        SendMessage(text)

def Clone():
    #
    shutil.copy(f'{target_dir}{target_file}', f'{target_dir}{target_file}.diff')

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
