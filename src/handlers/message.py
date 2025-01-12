import os
import re
import copy
from handlers.secrets import BotEnv

forge_primary_prefix = r"^\[[0-9a-zA-Z]{9} [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}] \[Server thread/INFO] \[net\.minecraft\.server\.dedicated\.DedicatedServer/]: "
forge_secondary_prefix = r"^\[[0-9a-zA-Z]{9} [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}] \[Server thread/INFO] \[net\.minecraft\.server\.MinecraftServer/]: "
default_prefix = r"^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Server thread/INFO]: "
prefix_wildcard_without_brackets = (
    f"{forge_primary_prefix}|{forge_secondary_prefix}|{default_prefix}"
)

def _get_ignore_names() -> list[str]:
    ignore_names = []
    if BotEnv.PluginDir.get() != "":
        ignore_names = os.listdir(BotEnv.PluginDir.get())

    # 名前としてみなさない文字列
    if BotEnv.OtherIgnoreNames.get() != "":
        ignore_names.extend(BotEnv.OtherIgnoreNames.get())

    # 拡張子、大文字小文字を無視
    raw_ignore_names = copy.deepcopy(ignore_names)

    for i, a in enumerate(raw_ignore_names):
        ignore_names.append(os.path.splitext(a)[0].casefold())
        ignore_names[i] = re.sub("[\_\-]([0-9]{1,}\.)+[0-9]{1,}", "", ignore_names[i])
    
    return ignore_names

class MessageConverter:
    def __init__(
        self,
        server_start_message: str,
        server_stop_message: str,
        server_restart_message: str,
        restart_announcement_message: str
    ):
        self.server_start_message = server_start_message
        self.server_stop_message = server_stop_message
        self.server_restart_message = server_restart_message
        self.restart_announcement_message = restart_announcement_message
        self.ignore_names = _get_ignore_names()
    
    def convert(self, text: str) -> dict | None:
        print(text)
        # 参加メッセージ
        # When someone joined
        match = re.findall(
            f"({prefix_wildcard_without_brackets})" + r"(.*) joined the game", text
        )
        if len(match) and not (str(match[0][1]).startswith("[")):
            player_count += 1
            chat_count = 0
            return {
                "embed": {
                    "color": "#0c0",
                    "name": str(match[0][1]),
                    "title": f"サーバーに参加しました。一緒に遊んであげよう！\n（現在 {player_count} 名）",
                },
                "noembed": {
                    "type": "normal",
                    "name": str(match[0][1]),
                    "message": f":green_circle: {str(match[0][1])} が参加しました。一緒に遊んであげよう！（現在 {player_count} 名）",
                },
            }
        # 退出メッセージ
        # When someone left
        match = re.findall(
            f"({prefix_wildcard_without_brackets})" + r"(.*) left the game", text
        )
        if len(match):
            player_count -= 1
            chat_count = 0
            return {
                "embed": {
                    "color": "#c00",
                    "name": str(match[0][1]),
                    "title": f"サーバーから退室しました。\n（現在 {player_count} 名）",
                },
                "noembed": { # TODO: fix this
                    "type": "normal",
                    "name": str(match[0][1]),
                    "message": f":red_circle: {str(match[0][1])} が退出しました。（現在 {player_count} 名）",
                },
            }
        # サーバー起動メッセージ
        # When your server is launched
        match = re.findall(f"({prefix_wildcard_without_brackets})" + r"Done ", text)
        if (
            len(match)
            and self.server_start_message != ""
            and status != "online"
        ):
            status = "online"
            player_count = 0
            return {
                "noembed": {
                    "type": "server_start",
                    "name": "server",
                    "message": self.server_start_message,
                }
            }
        # サーバー終了メッセージ
        # When your server is closed
        match = re.findall(
            f"({prefix_wildcard_without_brackets})" + r"Stopping( the)? server", text
        )
        # For Forge Dedicated Server
        if (
            len(match)
            and self.server_stop_message != ""
            and status != "restarting"
            and status != "closing"
        ):
            status = "closing"
            player_count = 0
            return {
                "noembed": {
                    "type": "server_stop",
                    "name": "server",
                    "message": self.server_stop_message,
                }
            }
        # サーバー再起動メッセージ
        # When your server is restarting
        match = re.findall(
            f"({prefix_wildcard_without_brackets})" + r"(\[Not Secure] |)\[Server] (.*)",
            text,
        )
        if len(match) and match[0][2] == self.restart_announcement_message:
            status = "restarting"
            return {
                "noembed": {
                    "type": "server_restart",
                    "name": "server",
                    "message": self.server_restart_message,
                }
            }
        # その他好きに追加・削除可能（上にあるものもいらないやつは消してOK）
        # You can freely add or remove some messages above or below

        # セキュアなチャット
        # secure chat
        match = re.findall(
            "^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Async Chat Thread - #(.*)/INFO]: <(.*?)>(.*)",
            text,
        )
        if len(match):
            return {
                "embed": {
                    "color": "#888",
                    "name": str(match[0][1]),
                    "title": str(match[0][2]),
                },
                "noembed": {
                    "type": "normal",
                    "name": str(match[0][1]),
                    "message": f"`[{str(match[0][1])}] {str(match[0][2])}`",
                },
            }
        match = re.findall(f"({prefix_wildcard_without_brackets})" + r"<(.*?)>(.*)", text)
        if len(match) and not (str(match[0][1]).casefold() in self.ignore_names):
            return {
                "embed": {
                    "color": "#888",
                    "name": str(match[0][1]),
                    "title": str(match[0][2]),
                },
                "noembed": {
                    "type": "normal",
                    "name": str(match[0][1]),
                    "message": f"`[{str(match[0][1])}] {str(match[0][2])}`",
                },
            }
        # セキュアではないチャット
        # non-secure chat
        match = re.findall(
            "^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Async Chat Thread - #(.*)/INFO]: \[(.*?)] <(.*)>(.*)",
            text,
        )
        if len(match):
            print(str(match))
            return {
                "embed": {
                    "color": "#888",
                    "name": str(match[0][2]),
                    "title": str(match[0][3]),
                },
                "noembed": {
                    "type": "normal",
                    "name": str(match[0][2]),
                    "message": f"`[{str(match[0][2])}]{str(match[0][3])}`",
                },
            }

        # sayコマンド経由のチャット
        # chat sent by "say" command
        match = re.findall(
            f"({prefix_wildcard_without_brackets})" + r"(\[Not Secure] )?\[(.*?)] (.*)",
            text,
        )
        # 「Server」からのチャットはサーバーコンソール経由のチャットと判定
        # 画像： https://aosankaku.github.io/Send-Minecraft-notifications/img/server.drawio.png
        if len(match) and str(match[0][2]) == "Server":
            print(str(match))
            return {
                "embed": {
                    "color": "#888",
                    "name": "#server",
                    "title": str(match[0][3]),
                },
                "noembed": {
                    "type": "normal",
                    "name": "#server",
                    "message": f"`[{str(match[0][2])}] {str(match[0][3])}`",
                },
            }
        # 上記以外
        if len(match) and not (str(match[0][2]).casefold() in self.ignore_names):
            print(str(match))
            return {
                "embed": {
                    "color": "#888",
                    "name": str(match[0][2]),
                    "title": str(match[0][3]),
                },
                "noembed": {
                    "type": "normal",
                    "name": str(match[0][2]),
                    "message": f"`[{str(match[0][2])}] {str(match[0][3])}`",
                },
            }

        # Lunachat対応コマンド
        # non-secure Luna chat(You don't need this unless someone uses Japanese in your server)
        match = re.findall(
            "^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Async Chat Thread - #(.*)/INFO]: (\[Not Secure] )?(.*): (.*)",
            text,
        )
        if len(match):
            print(str(match))
            return {
                "embed": {
                    "color": "#888",
                    "name": str(match[0][2]),
                    "title": str(match[0][3]),
                },
                "noembed": {
                    "type": "normal",
                    "name": str(match[0][2]),
                    "message": f"`[{str(match[0][2])}] {str(match[0][3])}`",
                },
            }

        # ホワイトリストに入ってない時の通知
        # join attempt from non-whitelisted player
        match = re.findall(
            f"({prefix_wildcard_without_brackets})"
            + r"Disconnecting (.*?name=)(.*?),(.*?You are not whitelisted on this server!)",
            text,
        )
        if len(match):
            print(str(match))
            return {
                "embed": {
                    "color": "#f8f",
                    "name": str(match[0][2]),
                    "title": "サーバーに入ろうとしましたが、ホワイトリストに入っていません！",
                },
                "noembed": {
                    "type": "normal",
                    "name": str(match[0][2]),
                    "message": f":yellow_circle: {str(match[0][2])} がサーバーに入ろうとしましたが、ホワイトリストに入っていません！",
                },
            }

        # プレイヤー数再計算
        # recalculate player count
        # ヒント：サーバーが「list」コマンドを使用してログを流すと、人数を再計算できます
        # Hint: The number of players will be recalculated whenever you issue the "/list" command from the console
        match = re.findall(
            f"({prefix_wildcard_without_brackets})"
            + r"There are ([0-9]*) of a max of ([0-9]*) players online:",
            text,
        )
        if len(match):
            player_count = int(match[0][1])
            chat_count = 0
            return {
                "embed": {
                    "color": "#f8f",
                    "name": str(match[0][2]),
                    "title": f":information_source: 現在サーバーにいるプレイヤーは {player_count} 人です。（上限 {str(match[0][2])} 名）",
                },
                "noembed": {
                    "type": "normal",
                    "name": str(match[0][2]),
                    "message": f":information_source: 現在サーバーにいるプレイヤーは {player_count} 人です。（上限 {str(match[0][2])} 名）",
                },
            }

        # 進捗通知
        # advancements
        match = re.findall(
            f"({prefix_wildcard_without_brackets})"
            + r"(.*) has made the advancement \[(.*)]",
            text,
        )
        if len(match):
            return {
                "embed": {
                    "color": "#f8f",
                    "name": str(match[0][1]),
                    "title": f":trophy: 進捗[{str(match[0][2])}]を達成しました！",
                },
                "noembed": {
                    "type": "normal",
                    "name": str(match[0][1]),
                    "message": f":trophy: {str(match[0][1])} が進捗[{str(match[0][2])}]を達成しました！",
                },
            }

        # 目標通知
        # goals
        match = re.findall(
            f"({prefix_wildcard_without_brackets})" + r"(.*) has reached the goal \[(.*)]",
            text,
        )
        if len(match):
            return {
                "embed": {
                    "color": "#f8f",
                    "name": str(match[0][1]),
                    "title": f":checkered_flag: 目標[{str(match[0][2])}]を達成しました！",
                },
                "noembed": {
                    "type": "normal",
                    "name": str(match[0][1]),
                    "message": f":checkered_flag: {str(match[0][1])} が目標[{str(match[0][2])}]を達成しました！",
                },
            }

        # 挑戦通知
        # challenges
        match = re.findall(
            f"({prefix_wildcard_without_brackets})"
            + r"(.*) has completed the challenge \[(.*)]",
            text,
        )
        if len(match):
            return {
                "embed": {
                    "color": "#f8f",
                    "name": str(match[0][1]),
                    "title": f":trophy: 進捗[{str(match[0][2])}]を達成しました！",
                },
                "noembed": {
                    "type": "normal",
                    "name": str(match[0][1]),
                    "message": f":trophy: {str(match[0][1])} が進捗[{str(match[0][2])}]を達成しました！",
                },
            }

        # 実績通知（～17w13a）
        # achievements(until 17w13a)
        match = re.findall(
            f"({prefix_wildcard_without_brackets})"
            + r"(.*) has just earned the achievement \[(.*)]",
            text,
        )
        if len(match):
            return {
                "embed": {
                    "color": "#f8f",
                    "name": str(match[0][1]),
                    "title": f":military_metal: 挑戦[{str(match[0][2])}]を達成しました！",
                },
                "noembed": {
                    "type": "normal",
                    "name": str(match[0][1]),
                    "message": f":military_metal: {str(match[0][1])} が挑戦[{str(match[0][2])}]を達成しました！",
                },
            }

        # 死亡通知（実験的機能）
        # death messages(experimental feature)
        match = re.findall(
            f"({prefix_wildcard_without_brackets})"
            + r"(.*) (was|died|drown|withered|experienced|blew|hit|fell|went|walked|burned|tried|discovered|froze|starved|suffocated|left) (.*)",
            text,
        )
        if len(match):
            return {
                "embed": {
                    "color": "#f8f",
                    "name": str(match[0][1]),
                    "title": f":skull_crossbones: 死んでしまいました。助けに行ってあげよう！",
                    "desc": f"{str(match[0][1])} {str(match[0][2])} {str(match[0][3])}",
                },
                "noembed": {
                    "type": "normal",
                    "name": str(match[0][1]),
                    "message": f":skull_crossbones: {str(match[0][1])} が死んでしまいました。助けに行ってあげよう！({str(match[0][1])} {str(match[0][2])} {str(match[0][3])})",
                },
            }
            return

        # 何もマッチしなかった場合はNoneを返す
        return None