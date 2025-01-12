import structlog
from message.parser import LogParser
from message.model import MessageData, MessageType

parser = LogParser()


logger: structlog.stdlib.BoundLogger = structlog.getLogger()

# Join Test
r = parser.parse("[01Dec2024 16:07:10.209] [Server thread/INFO] [net.minecraft.server.MinecraftServer/]: Ao_Sankaku joined the game")
logger.info(r)