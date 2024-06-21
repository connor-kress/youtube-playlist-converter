from dataclasses import dataclass
from mutagen.id3 import ID3, TIT2, TPE1, APIC  # type: ignore
from mutagen.mp3 import MP3
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
    audio = MP3(file_path, ID3=ID3)
    if audio.tags is None:
        audio.add_tags()
    assert audio.tags is not None
    tags = (
        TIT2(
            encoding=3,
            text=data.title,
        ),
        TPE1(
            encoding=3,
            text=data.artist,
        ),
        APIC(
            encoding=3,
            mime='image/jpeg',
            type=3,
            desc=u'Cover',
            data=data.cover_data,
        ),
    )
    for tag in tags:
        audio.tags.add(tag)
    audio.save()


metadata_functions: dict[str, Callable[[Path, Metadata], None]] = {
    "mp4": _set_mp4_metadata,
    "mp3": _set_mp3_metadata,
}
