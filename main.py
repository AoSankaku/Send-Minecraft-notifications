import os, re, time, requests, copy, random, chardet, warnings

from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver
from dotenv import load_dotenv
env = "./Send-Minecraft-notifications/.env"
load_dotenv(env)
with open(env, 'rb') as f:
    c = f.read()
    env_encode = chardet.detect(c)['encoding']

def ConvertStringToArray(target:str) :
    target = target[1:-1].replace("\"", "").replace(", ",",").replace(" ,",",")
    target = re.split(",", target)
    return target

def hexToInt(color_hex: str) -> int:
    if color_hex.startswith('#'):
        color_hex = color_hex[1:]  # #で始まるなら、'#'を取り除く
    return int(color_hex, 16)  # 16進数を整数に変換

webhook_url = os.environ.get("WEBHOOK_URL")
target_dir = os.environ.get("TARGET_DIR")
target_file = os.environ.get("TARGET_FILE")
plugin_dir = os.environ.get("PLUGIN_DIR")
other_ignore_names = os.environ.get("IGNORE_NAMES")
if other_ignore_names is not None and other_ignore_names != '':
    other_ignore_names = ConvertStringToArray(other_ignore_names)
kill_after_closed = os.environ.get("KILL_AFTER_CLOSED")
if kill_after_closed.upper() == "TRUE":
    kill_after_closed = True
elif kill_after_closed.upper() == "FALSE":
    kill_after_closed = False
else:
    raise KeyError(f"Invalid value set in your .env file: KILL_AFTER_CLOSED must be true or false, but your value is {kill_after_closed}")
server_start_message = os.environ.get("SERVER_START_MESSAGE")
server_stop_message = os.environ.get("SERVER_STOP_MESSAGE")
server_restart_message = os.environ.get("SERVER_RESTART_MESSAGE")
restart_announcement_message = os.environ.get("RESTART_ANNOUNCEMENT_MESSAGE")
tips_prefix = os.environ.get("TIPS_PREFIX")
if tips_prefix is None:
    tips_prefix = ""
tips_messages = os.environ.get("TIPS_MESSAGES")
if tips_messages is not None and tips_messages != '':
    tips_messages = ConvertStringToArray(tips_messages)
embed_mode = os.environ.get("EMBED_MODE")
if embed_mode.upper() == "TRUE":
    embed_mode = True
elif embed_mode.upper() == "FALSE":
    embed_mode = False
else:
    warnings.warn(f"Invalid value set in your .env file: EMBED_MODE must be true or false, but your value is {kill_after_closed}")
    embed_mode = False
sender_name = os.environ.get("SENDER_NAME")
sender_icon = os.environ.get("SENDER_ICON")
player_icon_api = os.environ.get("PLAYER_ICON_API")


forge_primary_prefix = "^\[[0-9a-zA-Z]{9} [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}] \[Server thread/INFO] \[net\.minecraft\.server\.dedicated\.DedicatedServer/]: "
forge_secondary_prefix = "^\[[0-9a-zA-Z]{9} [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}] \[Server thread/INFO] \[net\.minecraft\.server\.MinecraftServer/]: "
default_prefix = "^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Server thread/INFO]: "
prefix_wildcard_without_brackets = f"{forge_primary_prefix}|{forge_secondary_prefix}|{default_prefix}"

prev = []
player_count = 0
chat_count = 0
# status = "init" or "online" or "closing" or "restarting"
# この数値は好きに利用してください
# You can read this variable if you need
status = "init"
player_name = ""
server_console_name = "SERVER-CONSOLE-NAME!"
default_server_console_pic = "https://aosankaku.github.io/Send-Minecraft-notifications/img/server.drawio.png"

# プラグイン名を取得、フォルダーがなければ空配列を作成
# Fetching names of plugins. If none, creates an empty array

if plugin_dir is None or plugin_dir == '':
    ignore_names = []
else:
    ignore_names = os.listdir(plugin_dir)

# 名前としてみなさない文字列
if other_ignore_names is not None and other_ignore_names != '':
    ignore_names.extend(other_ignore_names)

# 拡張子、大文字小文字を無視
raw_ignore_names = copy.deepcopy(ignore_names)

for i, a in enumerate(raw_ignore_names):
    ignore_names.append(os.path.splitext(a)[0].casefold())
    ignore_names[i] = re.sub("[\_\-]([0-9]{1,}\.)+[0-9]{1,}", "", ignore_names[i])

print(ignore_names)


def SendMessage(message: dict) -> None:
    global chat_count, player_count, status, player_name
    embed = message.get("embed")
    if embed_mode and embed:
        main_content = {
            "content": "",
            "tts": False,
            "embeds": [
                {
                    "title": embed.get("title"),
                    "description": embed.get("desc", ""),
                    "color": hexToInt(embed.get("color", 0)),
                    "author": {
                        "name": "Server" if embed.get("name") == server_console_name else embed.get("name"),
                        "icon_url": default_server_console_pic if embed.get("name") == server_console_name else f"{player_icon_api}{embed.get("name")}",
                    },
                    "fields": [],
                }
            ],
            "components": [],
            "actions": {},
            "username": sender_name,
            "avatar_url": sender_icon,
        }

        print(main_content)
        
        requests.post(webhook_url, json=main_content)
    else:
        # discord以外のサービスのwebhookの場合はここを変更してください
        # If you wish to use services other than discord, customize here based on your service:
        main_content = {
            "content": message["message"],
        }
        if embed_mode:
            main_content["username"] = sender_name
            main_content["avatar_url"] = sender_icon
        requests.post(webhook_url, json=main_content)
    
    chat_count += 1

    # メッセージ定義
    player_count_notify_message = {"content": f':information_source: 現在サーバーにいるプレイヤーは {player_count} 人です。みんな待ってるよ:eyes:'}
    
    # 16回ログを流したら、追加で人数を送信
    if (chat_count == 16):
        chat_count = 0
        requests.post(webhook_url, player_count_notify_message)
    # restartの場合またはチャットが8回流れるごとに、追加でtipsを送信
    if (message == server_restart_message or (chat_count % 8 == 0 and chat_count % 16 != 0 and chat_count != 0)):
        prefix = str(tips_prefix).replace("\\n","\n")
        tip = str(tips_messages[random.randrange(len(tips_messages))]).replace("\\n","\n")
        requests.post(webhook_url, {"content": prefix.encode(env_encode) + tip.encode(env_encode)})

def MessageCreation(text: str):
    global status, ignore_names, player_count, chat_count
    print(text)
    # 参加メッセージ
    # When someone joined
    match = re.findall(f"({prefix_wildcard_without_brackets})" + r"(.*) joined the game", text)
    if (len(match) and not(str(match[0][1]).startswith("["))) :
        player_count += 1
        chat_count = 0
        return {
            "embed": {
                "color": "#0c0",
                "name": str(match[0][1]),
                "title": f"サーバーに参加しました。一緒に遊んであげよう！\n（現在 {player_count} 名）"
            },
            "noembed": {
                "type": "normal",
                "message": f":green_circle: {str(match[0][1])} が参加しました。一緒に遊んであげよう！（現在 {player_count} 名）"
            },
        }
    # 退出メッセージ
    # When someone left
    match = re.findall(f"({prefix_wildcard_without_brackets})" + r"(.*) left the game", text)
    if len(match) :
        player_count -= 1
        chat_count = 0
        return {
            "embed": {
                "color": "#c00",
                "name": str(match[0][1]),
                "title": f"サーバーから退室しました。\n（現在 {player_count} 名）"
            },
            "noembed": {
                "type": "normal",
                "message": f":red_circle: {str(match[0][1])} が退出しました。（現在 {player_count} 名）"
            },
        }
    # サーバー起動メッセージ
    # When your server is launched
    match = re.findall(f"({prefix_wildcard_without_brackets})" + r"Done ", text)
    if len(match) and server_start_message is not None and server_start_message != '' :
        status = "online"
        player_count = 0
        return {
            "noembed": {
                "type": "server_start",
                "message": server_start_message,
            }
        }
    # サーバー終了メッセージ
    # When your server is closed
    match = re.findall(f"({prefix_wildcard_without_brackets})" + r"Stopping( the)? server", text)
    # For Forge Dedicated Server
    if len(match) and server_stop_message is not None and server_stop_message != '' and status != "restarting" :
        status = "closing"
        player_count = 0
        return {
            "noembed": {
                "type": "server_stop",
                "message": server_stop_message,
            }
        }
    # サーバー再起動メッセージ
    # When your server is restarting
    match = re.findall(f"({prefix_wildcard_without_brackets})" + r"(\[Not Secure] |)\[Server] (.*)", text)
    if len(match) and match[0][2] == restart_announcement_message:
        status = "restarting"
        return {
            "noembed": {
                "type": "server_restart",
                "message": server_restart_message,
            }
        }
    # その他好きに追加・削除可能（上にあるものもいらないやつは消してOK）
    # You can freely add or remove some messages above or below

    # セキュアなチャット
    # secure chat
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Async Chat Thread - #(.*)/INFO]: <(.*?)>(.*)", text)
    if len(match) :
        return {
            "embed": {
                "color": "#888",
                "name": str(match[0][1]),
                "title": str(match[0][2]),
            },
            "noembed": {
                "type": "normal",
                "message": f'`[{str(match[0][1])}] {str(match[0][2])}`'
            },
        }
    match = re.findall(f"({prefix_wildcard_without_brackets})" + r"<(.*?)>(.*)", text)
    if len(match) and not(str(match[0][1]).casefold() in ignore_names):
        return {
            "embed": {
                "color": "#888",
                "name": str(match[0][1]),
                "title": str(match[0][2]),
            },
            "noembed": {
                "type": "normal",
                "message": f'`[{str(match[0][1])}] {str(match[0][2])}`'
            },
        }
    # セキュアではないチャット
    # non-secure chat
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Async Chat Thread - #(.*)/INFO]: \[(.*?)] <(.*)>(.*)", text)
    if len(match) :
        print(str(match))
        return {
            "embed": {
                "color": "#888",
                "name": str(match[0][2]),
                "title": str(match[0][3]),
            },
            "noembed": {
                "type": "normal",
                "message": f'`[{str(match[0][2])}]{str(match[0][3])}`'
            },
        }

    # sayコマンド経由のチャット
    # chat sent by "say" command
    match = re.findall(f"({prefix_wildcard_without_brackets})" + r"(\[Not Secure] )?\[(.*?)] (.*)", text)
    # 「Server」からのチャットはサーバーコンソール経由のチャットと判定
    # 画像：　https://aosankaku.github.io/Send-Minecraft-notifications/img/server.drawio.png
    if len(match) and str(match[0][2]) == "Server" :
        print(str(match))
        return {
            "embed": {
                "color": "#888",
                "name": server_console_name,
                "title": str(match[0][2]),
                "desc": str(match[0][3]),
            },
            "noembed": {
                "type": "normal",
                "message": f'`[{str(match[0][2])}] {str(match[0][3])}`'
            },
        }
    # 上記以外
    if len(match) and not(str(match[0][2]).casefold() in ignore_names) :
        print(str(match))
        return {
            "embed": {
                "color": "#888",
                "name": str(match[0][2]),
                "title": str(match[0][3]),
            },
            "noembed": {
                "type": "normal",
                "message": f'`[{str(match[0][2])}] {str(match[0][3])}`'
            },
        }
    
    # Lunachat対応コマンド
    # non-secure Luna chat(You don't need this unless someone uses Japanese in your server)
    match = re.findall("^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Async Chat Thread - #(.*)/INFO]: (\[Not Secure] )?(.*): (.*)", text)
    if len(match) :
        print(str(match))
        return {
            "embed": {
                "color": "#888",
                "name": str(match[0][2]),
                "title": str(match[0][3]),
            },
            "noembed": {
                "type": "normal",
                "message": f'`[{str(match[0][2])}] {str(match[0][3])}`'
            },
        }
    
    # ホワイトリストに入ってない時の通知
    # join attempt from non-whitelisted player
    match = re.findall(f"({prefix_wildcard_without_brackets})" + r"Disconnecting (.*?name=)(.*?),(.*?You are not whitelisted on this server!)", text)
    if len(match) :
        print(str(match))
        return {
            "embed": {
                "color": "#f8f",
                "name": str(match[0][2]),
                "title": "サーバーに入ろうとしましたが、ホワイトリストに入っていません！",
            },
            "noembed": {
                "type": "normal",
                "message": f':yellow_circle: {str(match[0][2])} がサーバーに入ろうとしましたが、ホワイトリストに入っていません！'
            },
        }
    
    # プレイヤー数再計算
    # recalculate player count
    # ヒント：サーバーが「list」コマンドを使用してログを流すと、人数を再計算できます
    # Hint: The number of players will be recalculated whenever you issue the "/list" command from the console
    match = re.findall(f"({prefix_wildcard_without_brackets})" + r"There are ([0-9]*) of a max of ([0-9]*) players online:", text)
    if len(match) :
        player_count = int(match[0][1])
        chat_count = 0
        return {
            "embed": {
                "color": "#f8f",
                "name": str(match[0][2]),
                "title": f':information_source: 現在サーバーにいるプレイヤーは {player_count} 人です。（上限 {str(match[0][2])} 名）',
            },
            "noembed": {
                "type": "normal",
                "message": f':information_source: 現在サーバーにいるプレイヤーは {player_count} 人です。（上限 {str(match[0][2])} 名）'
            },
        }
    
    # 進捗通知
    # advancements
    match = re.findall(f"({prefix_wildcard_without_brackets})" + r"(.*) has made the advancement \[(.*)]", text)
    if len(match) :
        return {
            "embed": {
                "color": "#f8f",
                "name": str(match[0][1]),
                "title": f':trophy: 進捗[{str(match[0][2])}]を達成しました！',
            },
            "noembed": {
                "type": "normal",
                "message": f':trophy: {str(match[0][1])} が進捗[{str(match[0][2])}]を達成しました！'
            },
        }
    
    # 目標通知
    # goals
    match = re.findall(f"({prefix_wildcard_without_brackets})" + r"(.*) has reached the goal \[(.*)]", text)
    if len(match) :
        return {
            "embed": {
                "color": "#f8f",
                "name": str(match[0][1]),
                "title": f':checkered_flag: 目標[{str(match[0][2])}]を達成しました！',
            },
            "noembed": {
                "type": "normal",
                "message": f':checkered_flag: {str(match[0][1])} が目標[{str(match[0][2])}]を達成しました！'
            },
        }

    # 挑戦通知
    # challenges
    match = re.findall(f"({prefix_wildcard_without_brackets})" + r"(.*) has completed the challenge \[(.*)]", text)
    if len(match) :
        return {
            "embed": {
                "color": "#f8f",
                "name": str(match[0][1]),
                "title": f':trophy: 進捗[{str(match[0][2])}]を達成しました！',
            },
            "noembed": {
                "type": "normal",
                "message": f':trophy: {str(match[0][1])} が進捗[{str(match[0][2])}]を達成しました！'
            },
        }

    # 実績通知（～17w13a）
    # achievements(until 17w13a)
    match = re.findall(f"({prefix_wildcard_without_brackets})" + r"(.*) has just earned the achievement \[(.*)]", text)
    if len(match) :
        return {
            "embed": {
                "color": "#f8f",
                "name": str(match[0][1]),
                "title": f':military_metal: 挑戦[{str(match[0][2])}]を達成しました！',
            },
            "noembed": {
                "type": "normal",
                "message": f':military_metal: {str(match[0][1])} が挑戦[{str(match[0][2])}]を達成しました！'
            },
        }

    # 死亡通知（実験的機能）
    # death messages(experimental feature)
    match = re.findall(f"({prefix_wildcard_without_brackets})" + r"(.*) (was|died|drown|withered|experienced|blew|hit|fell|went|walked|burned|tried|discovered|froze|starved|suffocated|left) (.*)", text)
    if len(match) :
        return {
            "embed": {
                "color": "#f8f",
                "name": str(match[0][1]),
                "title": f':skull_crossbones: 死んでしまいました。助けに行ってあげよう！',
                "desc": f'{str(match[0][1])} {str(match[0][2])} {str(match[0][3])}'
            },
            "noembed": {
                "type": "normal",
                "message": f':skull_crossbones: {str(match[0][1])} が死んでしまいました。助けに行ってあげよう！({str(match[0][1])} {str(match[0][2])} {str(match[0][3])})'
            },
        }
        return 
    
    # 何もマッチしなかった場合はNoneを返す
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
        data = MessageCreation(e)
        if data is not None:
            if embed_mode and data.get('embed', None) is not None:
                SendMessage(data)
            else:
                SendMessage(data['noembed'])

    # サーバーの終了を検知したらスクリプト停止
    if(status == "closing") and kill_after_closed:
        print("Server closing detected! Terminating script...")
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
