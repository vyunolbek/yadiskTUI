import os
from typing import Optional

from yadisk import AsyncClient

from yadisk_cli.config import load_token, get_active_account
from yadisk_cli.progress import CountingFile, TransferTracker


async def get_async_client(account_name: Optional[str] = None) -> Optional[AsyncClient]:
    if account_name is None:
        account_name = get_active_account()
    token_data = load_token(account_name)
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


async def _count_files_and_size(client: AsyncClient, path: str) -> tuple[int, int]:
    count = 0
    total = 0
    async for item in client.listdir(path):
        if item.type == "dir":
            c, s = await _count_files_and_size(client, item.path)
            count += c
            total += s
        else:
            count += 1
            total += getattr(item, "size", 0)
    return count, total


async def download_file_with_progress(client: AsyncClient, remote_path: str, local_path: str, tracker: TransferTracker):
    meta = await client.get_meta(remote_path)
    file_size = getattr(meta, "size", 0)
    name = os.path.basename(remote_path.rstrip("/"))
    tracker.start(total_bytes=file_size, total_files=1)
    tracker.start_file(name)
    cf = CountingFile(local_path, tracker)
    try:
        await client.download(remote_path, cf)
    finally:
        cf.close()
    tracker.finish()


async def download_dir_with_progress(
    client: AsyncClient, remote_path: str, local_path: str, tracker: TransferTracker
):
    name = os.path.basename(remote_path.rstrip("/"))
    nfiles, total = await _count_files_and_size(client, remote_path)
    tracker.start(total_bytes=total, total_files=nfiles)
    await _download_dir_recursive(client, remote_path, local_path, tracker)
    tracker.finish()


async def _download_dir_recursive(
    client: AsyncClient, remote_path: str, local_path: str, tracker: TransferTracker
):
    os.makedirs(local_path, exist_ok=True)
    async for item in client.listdir(remote_path):
        item_remote = item.path
        item_local = os.path.join(local_path, item.name)
        if item.type == "dir":
            await _download_dir_recursive(client, item_remote, item_local, tracker)
        else:
            file_size = getattr(item, "size", 0)
            tracker.start_file(item.name)
            cf = CountingFile(item_local, tracker)
            try:
                await client.download(item_remote, cf)
            finally:
                cf.close()


async def download_item_with_progress(
    client: AsyncClient, remote_path: str, local_path: str, item_type: str, tracker: TransferTracker
):
    if item_type == "dir":
        await download_dir_with_progress(client, remote_path, local_path, tracker)
    else:
        await download_file_with_progress(client, remote_path, local_path, tracker)


async def get_disk_info(client: AsyncClient):
    return await client.get_disk_info()
