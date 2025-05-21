import requests

from utils.miscutil import hex_to_int
from message.webhook import DiscordWebhook

class MessageSender:
    def __init__(self, webhook: DiscordWebhook, tips_messages: list[str], player_icon_api: str):
        self.chat_count = 0
        self.webhook = webhook
        self.tips_messages = tips_messages
        self.player_icon_api = player_icon_api
    
    async def onSendMessage(self):
        self.chat_count += 1
    
    async def SendMessage(self, message: dict) -> None:
        no_embed: dict[str, str] = message.get("noembed")
        name: str = no_embed.get("name")
        message: str = no_embed.get("message")
        if name == "#server":
            await self.webhook.sendServerMessage(message)
        else:
            await self.webhook.sendPlayerMessage(message, name)
        
        await self.onSendMessage()
        return
        
        embed = message.get("embed")
        if embed:
            main_content = {
                "content": "",
                "tts": False,
                "embeds": [
                    {
                        "title": embed.get("title"),
                        "description": embed.get("desc", ""),
                        "color": hex_to_int(embed.get("color", 0)),
                        "author": {
                            "name": (
                                "Server"
                                if embed.get("name") == "#server"
                                else embed.get("name")
                            ),
                            "icon_url": (
                                default_server_console_pic
                                if embed.get("name") == "#server"
                                else f"{self.player_icon_api}{embed.get("name")}"
                            ),
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
            requests.post(webhook_url, json=main_content)

        chat_count += 1

        # メッセージ定義
        player_count_notify_message = {
            "content": f":information_source: 現在サーバーにいるプレイヤーは {player_count} 人です。みんな待ってるよ:eyes:"
        }

        # 16回ログを流したら、追加で人数を送信
        if chat_count == 16:
            chat_count = 0
            requests.post(webhook_url, player_count_notify_message)
        # restartの場合またはチャットが8回流れるごとに、追加でtipsを送信
        if message == server_restart_message or (
            chat_count % 8 == 0 and chat_count % 16 != 0 and chat_count != 0
        ):
            prefix = str(tips_prefix).replace("\\n", "\n")
            tip = str(tips_messages[random.randrange(len(tips_messages))]).replace(
                "\\n", "\n"
            )
            requests.post(
                webhook_url, {"content": prefix.encode(env_encode) + tip.encode(env_encode)}
            )