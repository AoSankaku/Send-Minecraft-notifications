import os
import copy
from typing import Callable
from handlers.secrets import BotEnv
from watchdog.events import FileSystemEventHandler

class ChangeHandler(FileSystemEventHandler):
    def __init__(self, on_log_modified: Callable[[str], None]):
        super().__init__()
        self.on_log_modified = on_log_modified
    
    # フォルダ変更時のイベント
    def on_modified(self, event):
        filepath = event.src_path

        # ファイルでない場合無視する
        if os.path.isfile(filepath) is False:
            return

        # 監視対応のファイルでない場合無視する
        filename = os.path.basename(filepath)
        if filename != BotEnv.TargetFile.get():
            return

        self.on_log_modified(filepath)