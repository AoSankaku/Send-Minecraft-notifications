import asyncio
from server.server import Server

async def main():
    server = Server()
    server.init()
    await server.listen_file_change()
    server.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
