"""
FastTelethon: Parallelized, high-throughput multipart uploader for Telethon.
Optimized for 512KB chunks uploaded concurrently over multiple connection workers.
"""

import os
import math
import asyncio
import inspect
from telethon import utils, helpers
from telethon.tl import types, functions


async def _upload_part(client, file_id, part_index, chunk, is_big):
    if is_big:
        req = functions.upload.SaveBigFilePartRequest(
            file_id=file_id,
            file_part=part_index,
            file_total_parts=-1,
            bytes=chunk
        )
    else:
        req = functions.upload.SaveFilePartRequest(
            file_id=file_id,
            file_part=part_index,
            bytes=chunk
        )
    return await client(req)


async def fast_upload_file(client, file_path, progress_callback=None, max_workers=8):
    """
    Upload a file at high speed by chunking into 512KB parts and uploading concurrently.
    """
    file_size = os.path.getsize(file_path)
    part_size = 512 * 1024  # Maximum Telegram part size
    part_count = math.ceil(file_size / part_size) or 1
    is_big = file_size > 10 * 1024 * 1024  # >10MB uses SaveBigFilePart
    file_id = helpers.generate_random_long()

    uploaded_bytes = 0
    lock = asyncio.Lock()

    async def worker(queue):
        nonlocal uploaded_bytes
        while True:
            item = await queue.get()
            if item is None:
                queue.task_done()
                break
            part_index, chunk = item
            try:
                await _upload_part(client, file_id, part_index, chunk, is_big)
                async with lock:
                    uploaded_bytes += len(chunk)
                    if progress_callback:
                        res = progress_callback(uploaded_bytes, file_size)
                        if inspect.isawaitable(res):
                            await res
            finally:
                queue.task_done()

    queue = asyncio.Queue(maxsize=max_workers * 2)
    workers = [asyncio.create_task(worker(queue)) for _ in range(max_workers)]

    # Read and feed chunks into queue
    with open(file_path, "rb") as f:
        for part_index in range(part_count):
            chunk = f.read(part_size)
            await queue.put((part_index, chunk))

    # Wait for queue to finish
    await queue.join()

    # Cancel workers
    for _ in workers:
        await queue.put(None)
    await asyncio.gather(*workers)

    name = os.path.basename(file_path)
    if is_big:
        return types.InputFileBig(
            id=file_id,
            parts=part_count,
            name=name
        )
    else:
        # Standard MD5 is not strictly validated if parts match count
        return types.InputFile(
            id=file_id,
            parts=part_count,
            name=name,
            md5_checksum=""
        )
