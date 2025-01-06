import os
import warnings
import chardet
import copy
import re

from utils.miscutil import convert_string_to_array

from dotenv import load_dotenv

env = "./Send-Minecraft-notifications/.env"
load_dotenv(env)
with open(env, "rb") as f:
    c = f.read()
    env_encode = chardet.detect(c)["encoding"]

webhook_url = os.environ.get("WEBHOOK_URL")
target_dir = os.environ.get("TARGET_DIR")
target_file = os.environ.get("TARGET_FILE")
plugin_dir = os.environ.get("PLUGIN_DIR")
other_ignore_names = os.environ.get("IGNORE_NAMES")

if other_ignore_names is not None and other_ignore_names != "":
    other_ignore_names = convert_string_to_array(other_ignore_names)
kill_after_closed = os.environ.get("KILL_AFTER_CLOSED")
# if kill_after_closed.upper() == "TRUE":
#     kill_after_closed = True
# elif kill_after_closed.upper() == "FALSE":
#     kill_after_closed = False
# else:
#     raise KeyError(
#         f"Invalid value set in your .env file: KILL_AFTER_CLOSED must be true or false, but your value is {kill_after_closed}"
#     )

server_start_message = os.environ.get("SERVER_START_MESSAGE")
server_stop_message = os.environ.get("SERVER_STOP_MESSAGE")
server_restart_message = os.environ.get("SERVER_RESTART_MESSAGE")
restart_announcement_message = os.environ.get("RESTART_ANNOUNCEMENT_MESSAGE")

tips_prefix = os.environ.get("TIPS_PREFIX")
# if tips_prefix is None:
#     tips_prefix = ""

tips_messages = os.environ.get("TIPS_MESSAGES")
if tips_messages is not None and tips_messages != "":
    tips_messages = convert_string_to_array(tips_messages)
embed_mode = os.environ.get("EMBED_MODE")
# if embed_mode.upper() == "TRUE":
#     embed_mode = True
# elif embed_mode.upper() == "FALSE":
#     embed_mode = False
# else:
#     warnings.warn(
#         f"Invalid value set in your .env file: EMBED_MODE must be true or false, but your value is {kill_after_closed}"
#     )
#     embed_mode = False

sender_name = os.environ.get("SENDER_NAME")
sender_icon = os.environ.get("SENDER_ICON")
player_icon_api = os.environ.get("PLAYER_ICON_API")

forge_primary_prefix = "^\[[0-9a-zA-Z]{9} [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}] \[Server thread/INFO] \[net\.minecraft\.server\.dedicated\.DedicatedServer/]: "
forge_secondary_prefix = "^\[[0-9a-zA-Z]{9} [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}] \[Server thread/INFO] \[net\.minecraft\.server\.MinecraftServer/]: "
default_prefix = "^\[[0-9]{2}:[0-9]{2}:[0-9]{2}] \[Server thread/INFO]: "
prefix_wildcard_without_brackets = (
    f"{forge_primary_prefix}|{forge_secondary_prefix}|{default_prefix}"
)

# status = "init" or "online" or "closing" or "restarting"
# この数値は好きに利用してください
# You can read this variable if you need
status = "init"
player_name = ""
server_console_name = "SERVER-CONSOLE-NAME!"
default_server_console_pic = (
    "https://aosankaku.github.io/Send-Minecraft-notifications/img/server.drawio.png"
)


# プラグイン名を取得、フォルダーがなければ空配列を作成
# Fetching names of plugins. If none, creates an empty array
ignore_names = []
if plugin_dir and plugin_dir != "":
    ignore_names = os.listdir(plugin_dir)

# 名前としてみなさない文字列
if other_ignore_names is not None and other_ignore_names != "":
    ignore_names.extend(other_ignore_names)

# 拡張子、大文字小文字を無視
raw_ignore_names = copy.deepcopy(ignore_names)

for i, a in enumerate(raw_ignore_names):
    ignore_names.append(os.path.splitext(a)[0].casefold())
    ignore_names[i] = re.sub("[\_\-]([0-9]{1,}\.)+[0-9]{1,}", "", ignore_names[i])