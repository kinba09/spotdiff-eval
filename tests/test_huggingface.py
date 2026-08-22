import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from spotdiff_eval.huggingface import DownloadError, _safe_relative_path, download_dataset


class HuggingFaceTests(unittest.TestCase):
    def test_rejects_unsafe_dataset_paths(self):
        with self.assertRaises(DownloadError):
            _safe_relative_path("../outside.json")

    def test_download_preserves_repository_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with patch(
                "spotdiff_eval.huggingface._list_dataset_files",
                return_value=["data/manifest.json", "images/scene.jpg"],
            ), patch("spotdiff_eval.huggingface._download_file") as download_file:
                result = download_dataset("Abnik/spotdiff-v1-dev", output)

            self.assertEqual(result.dataset, "Abnik/spotdiff-v1-dev")
            self.assertEqual(result.files, ["data/manifest.json", "images/scene.jpg"])
            self.assertEqual(download_file.call_count, 2)
            self.assertEqual(download_file.call_args_list[0].args[2], "data/manifest.json")

    def test_rejects_invalid_dataset_id(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(DownloadError):
                download_dataset("not-a-dataset-id", Path(directory))


if __name__ == "__main__":
    unittest.main()
