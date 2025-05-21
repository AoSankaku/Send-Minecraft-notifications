import copy
import time
import structlog
import asyncio
from utils.miscutil import convert_string_to_array
from handlers.sender import MessageSender
from message.webhook import DiscordWebhook
from handlers.secrets import BotEnv
from handlers.message import MessageConverter
from handlers.filechange import ChangeHandler
from watchdog.observers.polling import PollingObserver

# prev = []
# player_count = 0
# chat_count = 0

logger: structlog.stdlib.BoundLogger = structlog.getLogger()

testUsernames = ["sysnote8", "Ao_Sankaku", "kazu_gmx"]

status = "init"
player_name = ""
server_console_name = "SERVER-CONSOLE-NAME!"
default_server_console_pic = (
    "https://aosankaku.github.io/Send-Minecraft-notifications/img/server.drawio.png"
)


def GetLog(filepath: str):

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
    print(len(log))
    print(len(oldLog))

    # 送信メッセージ作成
    for e in diff:
        # data = MessageCreation(e)
        # if data is not None:
        #     if embed_mode and data.get("embed", None) is not None:
        #         SendMessage(data)
        #     else:
        #         SendMessage(data["noembed"])
        print(e)

    # # サーバーの終了を検知したらスクリプト停止
    # if (status == "closing") and kill_after_closed:
    #     print("Server closing detected! Terminating script...")
    #     exit(-1)


async def main():
    # initialize
    logger.info("Initializing...")

    # Initialize environments
    BotEnv.init()

    # Setup discord webhook
    webhook = DiscordWebhook(BotEnv.WebhookUrl.get(), BotEnv.PlayerIconApi.get(), default_server_console_pic)
    message_sender = MessageSender(
        webhook,
        convert_string_to_array(BotEnv.TipsMessages.get()),
        BotEnv.PlayerIconApi.get()
    )

    # Message Converter (Minecraft -> Discord)
    message_converter = MessageConverter(
        BotEnv.ServerStartMessage.get(),
        BotEnv.ServerStopMessage.get(),
        BotEnv.ServerRestartMessage.get(),
        BotEnv.RestartAnnouncementMessage.get(),
    )

    logger.info("Initialize completed!")
    await webhook.sendMessage("Send Minecraft Notificationsの起動が完了しました。")
    c = message_converter.convert("[21:09:07] [Server thread/INFO] [minecraft/MinecraftServer]: [Not Secure] [Server] hello")
    print(c)
    return

    # await webhook.sendPlayerMessage("hello world from test code!", "sysnote8")

    # for i in range(10):
    #     await webhook.sendPlayerMessage(f"TestMessage! {i}", testUsernames[i%len(testUsernames)])

    # On exit

    while 1:
        event_handler = ChangeHandler(GetLog)
        observer = PollingObserver()
        observer.schedule(event_handler, BotEnv.TargetDir.get(), recursive=True)
        observer.start()
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()

    await webhook.onClose()


if __name__ == "__main__":
    asyncio.run(main())
