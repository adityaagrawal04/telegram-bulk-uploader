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

    def test_state_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = os.path.join(tmpdir, "state.json")
            with patch.object(uploader, "STATE_FILE", state_path):
                self.assertEqual(uploader.load_state(), set())
                uploader.save_state({"album/a.jpg", "album/b.mp4"})
                loaded = uploader.load_state()
                self.assertEqual(loaded, {"album/a.jpg", "album/b.mp4"})

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


if __name__ == "__main__":
    unittest.main()
