import asyncio
import traceback
from server.server import Server

async def main():
    server = Server()
    try:
        server.init()
        await server.listen_file_change()
    except KeyboardInterrupt:
        pass  # Suppress the default traceback
    except Exception as e:
        error_message = traceback.format_exc()
        print(error_message)
        if server.webhook:
            await server.webhook.sendServerMessage(f"An unexpected error occurred:\n```\n{error_message}```")
    finally:
        server.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
