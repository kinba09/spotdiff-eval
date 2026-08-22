"""Small, dependency-free downloader for public Hugging Face datasets."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


class DownloadError(RuntimeError):
    """Raised when a Hugging Face dataset cannot be listed or downloaded."""


_DATASET_ID = re.compile(r"^[^/\s]+/[^/\s]+$")
_USER_AGENT = "spotdiff-eval/0.2.0"


@dataclass(frozen=True)
class DownloadResult:
    dataset: str
    revision: str
    output_dir: Path
    files: List[str]


def _validate_dataset_id(dataset_id: str) -> str:
    if not isinstance(dataset_id, str) or not _DATASET_ID.fullmatch(dataset_id):
        raise DownloadError(
            f"invalid dataset id '{dataset_id}'; use the form 'username/dataset-name'"
        )
    return dataset_id


def _headers(token: Optional[str]) -> Dict[str, str]:
    result = {"User-Agent": _USER_AGENT}
    if token:
        result["Authorization"] = f"Bearer {token}"
    return result


def _request_json(url: str, token: Optional[str]) -> Any:
    request = urllib.request.Request(url, headers=_headers(token), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 401 or exc.code == 403:
            raise DownloadError("Hugging Face denied access to this dataset; check the dataset id and token") from exc
        raise DownloadError(f"Hugging Face returned HTTP {exc.code} while listing the dataset") from exc
    except urllib.error.URLError as exc:
        raise DownloadError(f"could not reach Hugging Face: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise DownloadError("Hugging Face returned an invalid file listing") from exc


def _list_dataset_files(dataset_id: str, revision: str, token: Optional[str]) -> List[str]:
    dataset_id = _validate_dataset_id(dataset_id)
    encoded_revision = urllib.parse.quote(revision, safe="")
    url = (
        f"https://huggingface.co/api/datasets/{dataset_id}/tree/{encoded_revision}"
        "?recursive=true&expand=false&limit=1000"
    )
    value = _request_json(url, token)
    if not isinstance(value, list):
        raise DownloadError("Hugging Face returned an unexpected dataset file listing")

    paths: List[str] = []
    for entry in value:
        if not isinstance(entry, dict) or entry.get("type") != "file":
            continue
        path = entry.get("path")
        if isinstance(path, str) and path:
            paths.append(path)
    if not paths:
        raise DownloadError(f"dataset '{dataset_id}' contains no downloadable files")
    return sorted(paths)


def _safe_relative_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise DownloadError(f"refusing unsafe dataset path '{value}'")
    return path


def _download_file(
    dataset_id: str,
    revision: str,
    path: str,
    output_dir: Path,
    token: Optional[str],
) -> None:
    encoded_revision = urllib.parse.quote(revision, safe="")
    encoded_path = urllib.parse.quote(path, safe="/")
    url = f"https://huggingface.co/datasets/{dataset_id}/resolve/{encoded_revision}/{encoded_path}?download=true"
    relative_path = _safe_relative_path(path)
    destination = output_dir / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".part")
    request = urllib.request.Request(url, headers=_headers(token), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
        temporary.replace(destination)
    except urllib.error.HTTPError as exc:
        if temporary.exists():
            temporary.unlink()
        if exc.code == 401 or exc.code == 403:
            raise DownloadError("Hugging Face denied access to this dataset; check the dataset id and token") from exc
        raise DownloadError(f"Hugging Face returned HTTP {exc.code} while downloading '{path}'") from exc
    except urllib.error.URLError as exc:
        if temporary.exists():
            temporary.unlink()
        raise DownloadError(f"could not download '{path}' from Hugging Face: {exc.reason}") from exc
    except OSError as exc:
        if temporary.exists():
            temporary.unlink()
        raise DownloadError(f"could not write '{destination}': {exc}") from exc


def download_dataset(
    dataset_id: str,
    output_dir: Path,
    revision: str = "main",
    token: Optional[str] = None,
) -> DownloadResult:
    """Download every file in a Hugging Face dataset repository.

    The repository-relative paths are preserved below ``output_dir``. This
    means a dataset containing ``data/manifest.json`` can be evaluated with
    the same manifest path after download.
    """

    dataset_id = _validate_dataset_id(dataset_id)
    if not revision.strip():
        raise DownloadError("revision must be a non-empty branch, tag, or commit")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = _list_dataset_files(dataset_id, revision, token)
    for path in paths:
        _download_file(dataset_id, revision, path, output_dir, token)
    return DownloadResult(dataset_id, revision, output_dir, paths)


def token_from_environment(name: Optional[str]) -> Optional[str]:
    """Read an optional Hugging Face token without printing it."""

    return os.environ.get(name) if name else None
