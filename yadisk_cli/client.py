from typing import AsyncIterator, Optional

from yadisk import AsyncClient

from yadisk_cli.config import load_token


async def get_async_client() -> Optional[AsyncClient]:
    token_data = load_token()
    if token_data is None:
        return None
    token = token_data.get("access_token")
    if not token:
        return None
    client = AsyncClient(token=token)
    try:
        if not await client.check_token():
            return None
    except Exception:
        return None
    return client


async def list_dir(client: AsyncClient, path: str = "/"):
    async for item in client.listdir(path):
        yield item


async def get_meta(client: AsyncClient, path: str):
    return await client.get_meta(path)


async def download_file(client: AsyncClient, remote_path: str, local_path: str):
    await client.download(remote_path, local_path)


async def get_disk_info(client: AsyncClient):
    return await client.get_disk_info()
