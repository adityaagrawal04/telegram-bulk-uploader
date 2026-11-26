"""
FastTelethon Turbo (Hardened): Robust parallel multipart uploader for Telethon.
- Fixes Telegram SaveBigFilePartRequest part_count specification.
- Uses borrowed exported senders safely with sender.send() or client fallback.
- Implements part-level retries and clean worker exception propagation to prevent deadlocks.
- Guarantees return of borrowed senders in try/finally.
"""

import os
import math
import asyncio
import inspect
from telethon import helpers
from telethon.tl import types, functions


async def _upload_part_with_retry(caller, req, max_retries=4):
    """Upload a single file part with retries on transient transport failures."""
    last_err = None
    for attempt in range(max_retries):
        try:
            if hasattr(caller, "send"):
                return await caller.send(req)
            else:
                return await caller(req)
        except Exception as e:
            last_err = e
            await asyncio.sleep(0.5 * (2 ** attempt))
    raise RuntimeError(f"Failed part upload after {max_retries} attempts: {last_err}")


async def _upload_worker(caller, file_id, queue, is_big, total_parts, on_part_done, failure_event):
    """Worker task that processes parts from queue until empty or failure signal."""
    while not failure_event.is_set():
        try:
            item = await asyncio.wait_for(queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            continue

        if item is None:
            queue.task_done()
            break

        part_index, chunk = item
        try:
            if is_big:
                req = functions.upload.SaveBigFilePartRequest(
                    file_id=file_id,
                    file_part=part_index,
                    file_total_parts=total_parts,
                    bytes=chunk
                )
            else:
                req = functions.upload.SaveFilePartRequest(
                    file_id=file_id,
                    file_part=part_index,
                    bytes=chunk
                )
            await _upload_part_with_retry(caller, req)
            await on_part_done(len(chunk))
        except Exception as e:
            failure_event.set()
            queue.task_done()
            raise e
        else:
            queue.task_done()


async def fast_upload_file(client, file_path, progress_callback=None, max_workers=16):
    """
    High-performance upload using concurrent workers.
    Safely borrows and returns exported senders if available, with full error recovery.
    """
    file_size = os.path.getsize(file_path)
    part_size = 512 * 1024  # 512KB Telegram standard
    part_count = math.ceil(file_size / part_size) or 1
    is_big = file_size > 10 * 1024 * 1024  # >10MB
    file_id = helpers.generate_random_long()

    if part_count <= 2:
        max_workers = min(part_count, 2)
    else:
        max_workers = min(max_workers, part_count, 16)

    senders = []
    # Safely borrow exported senders if Telethon supports it
    try:
        if hasattr(client, "_borrow_exported_sender"):
            dc_id = client.session.dc_id
            for _ in range(max_workers):
                s = await client._borrow_exported_sender(dc_id)
                senders.append(s)
    except Exception:
        senders = []

    uploaded_bytes = 0
    lock = asyncio.Lock()
    failure_event = asyncio.Event()

    async def on_part_done(chunk_len):
        nonlocal uploaded_bytes
        async with lock:
            uploaded_bytes += chunk_len
            if progress_callback:
                res = progress_callback(uploaded_bytes, file_size)
                if inspect.isawaitable(res):
                    await res

    queue = asyncio.Queue(maxsize=max_workers * 2)
    workers = []
    try:
        for i in range(max_workers):
            caller = senders[i] if i < len(senders) else client
            workers.append(
                asyncio.create_task(
                    _upload_worker(caller, file_id, queue, is_big, part_count, on_part_done, failure_event)
                )
            )

        # Producer feeds chunks
        with open(file_path, "rb") as f:
            for part_index in range(part_count):
                if failure_event.is_set():
                    break
                chunk = f.read(part_size)
                while not failure_event.is_set():
                    try:
                        await asyncio.wait_for(queue.put((part_index, chunk)), timeout=0.5)
                        break
                    except asyncio.TimeoutError:
                        continue

        if not failure_event.is_set():
            await queue.join()

        # Stop workers
        for _ in workers:
            try:
                queue.put_nowait(None)
            except Exception:
                pass

        # Check worker results
        results = await asyncio.gather(*workers, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                raise r

    finally:
        # Guarantee cancellation of any lingering workers
        for w in workers:
            if not w.done():
                w.cancel()
        # Guarantee return of borrowed senders
        if senders and hasattr(client, "_return_exported_sender"):
            for s in senders:
                try:
                    await client._return_exported_sender(s)
                except Exception:
                    pass

    name = os.path.basename(file_path)
    if is_big:
        return types.InputFileBig(id=file_id, parts=part_count, name=name)
    else:
        return types.InputFile(id=file_id, parts=part_count, name=name, md5_checksum="")
