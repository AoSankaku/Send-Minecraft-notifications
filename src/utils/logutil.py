import copy

class LogUtil:
    def __init__(self):
        self.prev: list[str] = []
    
    def load_to_prev(self, filepath: str):
        with open(filepath, "r", errors="ignore") as f:
            self.prev = f.readlines()
    
    def get_log_diff(self, filepath: str) -> list[str]:
        # 先に現在のログを取得（こっちを先にしないとずれる）
        with open(filepath, "r", errors="ignore") as f:
            log = f.readlines()
            # 前回のログを参照する
            oldLog = copy.deepcopy(self.prev)
            # oldLogに古いログが入っているのでprevを更新
            self.prev = copy.deepcopy(log)

        # どうやらサーバーをつけたまま日付をまたぐとlatest.logがまるっきり書き換わるらしいのでそれに対応できるように
        # 理論上、logはoldlogの中身を完全に包括しているはずなので、そうでない場合は「まるごと置き換わった」とみなす
        # oldLogとlogの時刻、長さを比べる方法やosの時間を比較する方法も浮かんだが、不具合を生む可能性が高いと判断した
        # 極稀に(log AND oldLog)に重複が生まれる可能性あり、将来的に対処が必要
        joinedLog = "\n".join(log)
        joinedOldLog = "\n".join(oldLog)
        if (
            # 判定条件：logがoldLogで始まらない（logはoldLogの延長でないと矛盾が生じる）＝日付をまたいだ
            # 「この配列で始まる」は原理的に不可能なので、文字列に変換して判定
            not (joinedLog.startswith(joinedOldLog))
        ):
            # いずれかに当てはまる場合はoldLogはなかったものとして削除する
            # こうすることでoldLogの長さは0になり、常にlogを読むようになる
            oldLog = []

        # oldLogとlogの排他的論理和だと「連続で同じ文字を送信した」などの特殊な状況の場合に反応しなくなるため
        # 「len(oldLog)-1の長さだけlogの要素を削除する」で決着
        del log[: len(oldLog)]
        diff = log
        # print(len(log))
        # print(len(oldLog))

        return diff
