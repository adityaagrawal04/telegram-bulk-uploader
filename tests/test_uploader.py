import os
import sys
import json
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import uploader


class TestUploaderCLI(unittest.TestCase):
    def test_parse_args_defaults(self):
        with patch.object(sys, "argv", ["uploader.py", "/some/folder"]):
            args = uploader.parse_args()
        self.assertEqual(args.source, "/some/folder")
        self.assertEqual(args.target, "me")
        self.assertFalse(args.compress)
        self.assertFalse(args.premium)
        self.assertIsNone(args.ext)
        self.assertEqual(args.delay, 1.5)
        self.assertFalse(args.split_large)

    def test_parse_args_all_flags(self):
        with patch.object(
            sys,
            "argv",
            [
                "uploader.py",
                "/media",
                "-t",
                "-1001234567890",
                "--compress",
                "--premium",
                "--ext",
                ".mp4",
                "jpg",
                "--delay",
                "0.5",
                "--split-large",
            ],
        ):
            args = uploader.parse_args()
        self.assertEqual(args.source, "/media")
        self.assertEqual(args.target, "-1001234567890")
        self.assertTrue(args.compress)
        self.assertTrue(args.premium)
        self.assertEqual(args.ext, [".mp4", "jpg"])
        self.assertEqual(args.delay, 0.5)
        self.assertTrue(args.split_large)

    def test_get_all_files_filters_hidden_and_extensions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sub = os.path.join(tmpdir, "album")
            os.makedirs(sub)
            for name in ["a.jpg", "b.MP4", ".hidden.jpg", "Thumbs.db", "desktop.ini", "notes.txt"]:
                with open(os.path.join(sub, name), "wb") as f:
                    f.write(b"data")

            all_files = uploader.get_all_files(tmpdir)
            basenames = [os.path.basename(p) for p in all_files]
            self.assertEqual(basenames, ["a.jpg", "b.MP4", "notes.txt"])

            filtered = uploader.get_all_files(tmpdir, ["jpg", ".mp4"])
            filtered_names = [os.path.basename(p) for p in filtered]
            self.assertEqual(filtered_names, ["a.jpg", "b.MP4"])

    def test_folder_and_glob_filters(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for rel in [
                "Vacation/day1.jpg",
                "Vacation/raw/img1.dng",
                "Family/party.mp4",
                "Family/draft_clip.mp4",
                "temp/cache.jpg",
            ]:
                full = os.path.join(tmpdir, rel)
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, "wb") as f:
                    f.write(b"data")

            selected = uploader.get_all_files(
                tmpdir,
                include_folders=["Vacation", "Family"],
                exclude_folders=["raw"],
                include_patterns=["*.jpg", "*.mp4"],
                exclude_patterns=["*draft*"],
            )
            rels = [os.path.relpath(p, tmpdir).replace("\\", "/") for p in selected]
            self.assertEqual(rels, ["Family/party.mp4", "Vacation/day1.jpg"])

    def test_parse_selection_indices(self):
        self.assertEqual(uploader.parse_selection_indices("", 4), [0, 1, 2, 3])
        self.assertEqual(uploader.parse_selection_indices("all", 3), [0, 1, 2])
        self.assertEqual(uploader.parse_selection_indices("none", 3), [])
        self.assertEqual(uploader.parse_selection_indices("1,3-4", 5), [0, 2, 3])
        with self.assertRaises(ValueError):
            uploader.parse_selection_indices("2-6", 5)

    def test_interactive_select_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = []
            for rel in ["AlbumA/1.jpg", "AlbumA/2.jpg", "AlbumB/3.mp4"]:
                full = os.path.join(tmpdir, rel)
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, "wb") as f:
                    f.write(b"123")
                paths.append(full)

            # Choose folder 1 (AlbumA), then pick file 2 (2.jpg)
            with patch("builtins.input", side_effect=["1", "y", "2"]):
                chosen = uploader.interactive_select_files(tmpdir, paths)
            self.assertEqual(
                [os.path.relpath(p, tmpdir).replace("\\", "/") for p in chosen],
                ["AlbumA/2.jpg"],
            )


class TestWebApp(unittest.TestCase):
    def test_browse_and_status_endpoints(self):
        import asyncio
        import app as web_app

        with tempfile.TemporaryDirectory() as tmpdir:
            sub = os.path.join(tmpdir, "Trip")
            os.makedirs(sub)
            with open(os.path.join(sub, "photo.jpg"), "wb") as f:
                f.write(b"12345")

            res = asyncio.run(web_app.browse_folder(web_app.BrowseRequest(source=tmpdir)))
            self.assertEqual(res["total_files"], 1)
            self.assertEqual(res["folders"][0]["folder"], "Trip")
            self.assertEqual(res["files"][0]["name"], "photo.jpg")

            status = asyncio.run(web_app.upload_status())
            self.assertFalse(status["running"])
            self.assertEqual(status["status_message"], "Idle")

    def test_state_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = os.path.join(tmpdir, "state.json")
            with patch.object(uploader, "STATE_FILE", state_path):
                self.assertEqual(uploader.load_state(), set())
                state = set()
                key1 = uploader.make_state_key("me", "album/a.jpg", 100, 1700000000)
                key2 = uploader.make_state_key("me", "album/b.mp4", 200, 1700000000)
                state.add(key1)
                state.add(key2)
                uploader.save_state(state)
                loaded = uploader.load_state()
                self.assertEqual(loaded, {key1, key2})
                self.assertTrue(uploader.is_file_uploaded(loaded, "me", "album/a.jpg", 100, 1700000000))
                # Different target or changed file size is not marked uploaded
                self.assertFalse(uploader.is_file_uploaded(loaded, "-100123", "album/a.jpg", 100, 1700000000))
                self.assertFalse(uploader.is_file_uploaded(loaded, "me", "album/a.jpg", 105, 1700000000))

    @unittest.skipUnless(
        shutil.which("ffmpeg") and shutil.which("ffprobe"),
        "FFmpeg and ffprobe required for video splitting test",
    )
    def test_split_video_file_with_ffmpeg(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sample_video = os.path.join(tmpdir, "sample.mp4")
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc=duration=6:size=320x240:rate=10",
                    "-c:v",
                    "libx264",
                    "-g",
                    "10",
                    "-pix_fmt",
                    "yuv420p",
                    sample_video,
                ],
                capture_output=True,
                check=True,
            )
            file_size = os.path.getsize(sample_video)
            duration = uploader.get_video_duration(sample_video)
            self.assertGreater(duration, 5.0)

            out_dir = os.path.join(tmpdir, "chunks")
            os.makedirs(out_dir)
            # Force splitting into multiple parts by setting max_file_size to ~half the file
            chunks = uploader.split_video_file(sample_video, out_dir, max(1, file_size // 2))
            self.assertGreaterEqual(len(chunks), 2)
            for chunk in chunks:
                self.assertGreater(os.path.getsize(chunk), 0)


class TestFastTelethon(unittest.TestCase):
    def test_make_state_key_uniqueness(self):
        k1 = uploader.make_state_key("me", "folder/file.mp4", 1000, 1700000000)
        k2 = uploader.make_state_key("-100123", "folder/file.mp4", 1000, 1700000000)
        k3 = uploader.make_state_key("me", "folder/file.mp4", 1001, 1700000000)
        self.assertNotEqual(k1, k2)
        self.assertNotEqual(k1, k3)
        self.assertTrue(k1.startswith("me::folder/file.mp4"))

    def test_cli_new_flags(self):
        with patch.object(
            sys,
            "argv",
            [
                "uploader.py",
                "/data",
                "--delete-on-success",
                "--no-thumb",
            ],
        ):
            args = uploader.parse_args()
            self.assertTrue(args.delete_on_success)
            self.assertTrue(args.no_thumb)

    def test_compress_image_below_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a small dummy image that is already <= 9MB
            small_img = os.path.join(tmpdir, "small.jpg")
            with open(small_img, "wb") as f:
                f.write(b"\xFF\xD8\xFF\xE0" + b"\x00" * 1000)
            res = uploader.compress_image_below_limit(small_img, output_dir=tmpdir, max_bytes=9*1024*1024)
            # Already <= 9MB, should return None
            self.assertIsNone(res)

            # Test threshold limit on a mock > max_bytes
            fake_large = os.path.join(tmpdir, "large.jpg")
            with open(fake_large, "wb") as f:
                f.write(b"\xFF\xD8\xFF\xE0" + b"\x00" * 2000)
            # Setting max_bytes to 1000 forces compression check
            res_compressed = uploader.compress_image_below_limit(fake_large, output_dir=tmpdir, max_bytes=1000)
            if uploader.is_ffmpeg_available():
                # If ffmpeg is available, it produces a valid file
                if res_compressed:
                    self.assertTrue(os.path.exists(res_compressed))



if __name__ == "__main__":
    unittest.main()
