"""Capture start retries when FFmpeg can't open the game window, before the game starts testing."""
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import recording as recorder_module


class FakeFFmpeg:
    def __init__(self, opens):
        self.returncode = None if opens else 1
        self.stdout = io.StringIO("frame=1\n" if opens else "")
        self.stdin = io.StringIO()

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode


class CaptureStartTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.run = Path(self.temp.name)
        (self.run / "capture-ready.json").write_text("{}")

    def tearDown(self):
        self.temp.cleanup()

    def drive(self, outcomes):
        recording = recorder_module.Recording("ffmpeg", self.run, 60)
        processes = iter(FakeFFmpeg(opens) for opens in outcomes)
        with mock.patch.object(recorder_module.subprocess, "Popen", side_effect=lambda *a, **k: next(processes)), \
                mock.patch.object(recorder_module, "RETRY_DELAY", 0):
            for _ in range(20):
                recording.poll()
                recording.progress_thread.join(1)
                if recording.acknowledged or recording.done:
                    break
        return recording

    def test_retries_until_a_frame_is_captured(self):
        recording = self.drive([False, False, True])
        self.assertTrue(recording.acknowledged)
        self.assertIsNone(recording.error)
        self.assertEqual(recording.attempts, 3)
        self.assertTrue((self.run / "capture-started.json").is_file())
        self.assertIn("capture attempt 3 of 3", (self.run / "recording.log").read_text())
        recording.log.close()

    def test_gives_up_after_three_attempts_and_tells_the_game(self):
        recording = self.drive([False, False, False])
        self.assertIn("attempt 3 of 3", recording.error)
        self.assertTrue((self.run / "capture-failed.json").is_file())


if __name__ == "__main__":
    unittest.main()
