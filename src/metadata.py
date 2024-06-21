from dataclasses import dataclass
from mutagen.mp4 import MP4, MP4Cover
from pathlib import Path
from typing import Callable


@dataclass(kw_only=True)
class Metadata:
    title: str
    artist: str
    cover_data: bytes


def _set_mp4_metadata(file_path: Path, data: Metadata) -> None:
    """Sets an MP4 file's metadata."""
    cover = MP4Cover(data.cover_data, MP4Cover.FORMAT_JPEG)
    vid = MP4(file_path)
    vid["covr"] = [cover]
    vid["\xa9nam"] = [data.title]
    vid["\xa9ART"] = [data.artist]
    vid.save()


def _set_mp3_metadata(file_path: Path, data: Metadata) -> None:
    """Sets an MP3 file's metadata."""
    raise NotImplementedError()


metadata_functions: dict[str, Callable[[Path, Metadata], None]] = {
    "mp4": _set_mp4_metadata,
    "mp3": _set_mp3_metadata,
}
