import json
import sys

from os import PathLike
from pathlib import Path
from pathvalidate import sanitize_filename
from pytube import Playlist, Stream
from pytube.exceptions import AgeRestrictedError
from typing import Optional


class DownloadingError(Exception):
    """Basic class covering all posible errors encountered
    while downloading YouTube videos.
    """
    def __init__(self, msg: str) -> None:
        super().__init__()
        self.msg = msg


def readable_size(bytes: int) -> str:
    """Returns a human readable representation of a number of bytes."""
    if bytes < 1024:
        return f"{bytes} bytes"
    elif bytes < 1024**2:
        return f"{bytes/1024:.2f} KiB"
    elif bytes < 1024**3:
        return f"{bytes/1024**2:.2f} MiB"
    else:
        return f"{bytes/1024**3:.2f} GiB"


def time_distribute(secs: int) -> tuple[int, int, int]:
    """Divides seconds into a standard (seconds, minutes, hours) format."""
    mins, secs = divmod(secs, 60)
    hours, mins = divmod(mins, 60)
    return secs, mins, hours


def download_playlist(playlist_url: str, output: Optional[PathLike[str]]) -> None:
    """Downloads the audio from all videos in a specified YouTube playlist.
    Downloads into `~/Music/<TITLE>/` by default.

    # Parameters
    ------------
    * `playlist_url`: The URL to the YouTube playlist to be downloaded.
    * `output`: The directory all files will be downloaded into.

    # Examples
    ----------
    ```python
    url = input("Enter playlist url: ")
    path = input("Enter output path: ")
    try:
        download_playlist(url, path)
    except DownloadingError as e:
        print(e.msg)
    else:
        print("Success!")
    ```
    """
    playlist = Playlist(playlist_url)
    output_dir: Path
    if output is None:
        base_dir = Path.home() / "Music"
        if base_dir.is_file():
            raise DownloadingError(
                "File found at default directory (`~/Music`)"
            )
        if not base_dir.exists():
            base_dir.mkdir()
        output_dir = base_dir / sanitize_filename(playlist.title)
    else:
        if str(output).startswith("~"):
            output_dir = Path.home() / str(output).removeprefix("~")
        else:
            output_dir = Path(output)

    if output_dir.is_file():
        raise DownloadingError("Output path contains a file")
    if not output_dir.exists():
        output_dir.mkdir(parents=True)
    total_secs = 0
    bytes_downloaded = 0
    vids_downloaded = 0
    total_bytes = 0
    age_restricted_urls: list[str] = []
    info: list[dict[str, str]] = []
    print(f"Downloading playlist: {playlist.title}\n")
    for i, vid in enumerate(playlist.videos, start=1):
        stream: Optional[Stream]
        try:
            stream = vid.streams\
                        .filter(file_extension="mp4", only_audio=True)\
                        .first()
        except AgeRestrictedError:
            age_restricted_urls.append(vid.watch_url)
            print("Video is age restricted")
            continue
        if stream is None:
            print("No stream found")
            continue
        if not stream.includes_audio_track:
            print("Video has no audio")
            continue
        total_secs += vid.length
        secs, mins, hours = time_distribute(vid.length)
        file_name = f"{sanitize_filename(stream.title)}.mp4"
        file_path = output_dir / file_name
        if not file_path.is_file():
            print(f"Downloading {i}/{playlist.length}: {stream.title} "
                  f"({hours}:{mins:02d}:{secs:02d})",
                  end="", flush=True)
            stream.download(str(output_dir), file_name)
            vids_downloaded += 1
            file_size = file_path.stat().st_size
            bytes_downloaded += file_size
            total_bytes += file_size
            print(f" - {readable_size(file_size)}")
        else:
            file_size = file_path.stat().st_size
            total_bytes += file_size
            print(f"Found {i}/{playlist.length}: {stream.title} "
                  f"({hours}:{mins:02d}:{secs:02d})")
        info.append({
            "author": vid.author,
            "title": stream.title,
            "path": str(file_path),
        })
    with open(output_dir / "info.json", "w") as file:
        json.dump(info, file)
    secs, mins, hours = time_distribute(total_secs)

    print(f"\nFinished downloading playlist: {playlist.title}")
    if vids_downloaded == playlist.length:
        print(f"\tTotal videos: {playlist.length}")
    else:
        print(f"\tDownloaded videos: {vids_downloaded} / {playlist.length}")
    if bytes_downloaded == total_bytes:
        print(f"\tTotal size: {readable_size(bytes_downloaded)}")
    else:
        print(f"\tDownloaded size: {readable_size(bytes_downloaded)} / "
                                 f"{readable_size(total_bytes)}")
    print(f"\tTotal length: {hours} hours, {mins} mins, {secs} secs")
    if len(age_restricted_urls) != 0:
        print(f"\nAge restricted videos: ({len(age_restricted_urls)})")
        for restricted_url in age_restricted_urls:
            print(f"\t{restricted_url}")


def main() -> None:
    if len(sys.argv) < 2:
        print("No playlist URL provided", file=sys.stderr)
        exit(1)
    try:
        download_playlist(sys.argv[1], None)
    except DownloadingError as e:
        print(e.msg, file=sys.stderr)
        exit(1)


if __name__ == "__main__":
    main()
