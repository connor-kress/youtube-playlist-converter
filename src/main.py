import pytube
import requests
import sys

from moviepy.audio.io.AudioFileClip import AudioFileClip
from pathlib import Path
from pathvalidate import sanitize_filename
from pytube import Playlist, Stream
from pytube.exceptions import AgeRestrictedError
from typing import Callable, Optional

from metadata import Metadata, metadata_functions

class DownloadingError(Exception):
    """Basic class covering all posible errors encountered
    while downloading YouTube videos.
    """
    def __init__(self, msg: str) -> None:
        super().__init__()
        self.msg = msg


def format_size(size: int) -> str:
    """Returns a human readable representation of a number of bytes."""
    if size < 1024:
        return f"{size} bytes"
    elif size < 1024**2:
        return f"{size/1024:.2f} KiB"
    elif size < 1024**3:
        return f"{size/1024**2:.2f} MiB"
    else:
        return f"{size/1024**3:.2f} GiB"


def format_time(secs: int, long: bool = False) -> str:
    """Returns a formated time string given the total number of seconds."""
    mins, secs = divmod(secs, 60)
    hours, mins = divmod(mins, 60)
    parts: list[str] = []
    if long:
        if hours: parts.append(f"{hours} hours")
        if hours or mins: parts.append(f"{mins} mins")
        parts.append(f"{secs} secs")
        return ", ".join(parts)
    else:
        if hours: parts.append(f"{hours}h")
        if hours or mins: parts.append(f"{mins}m")
        parts.append(f"{secs}s")
        return " ".join(parts)


def get_and_validate_dir_path(output: Optional[str],
                              title: str,
                              only_audio: bool) -> Path:
    """Normalizes optional input to an absolute path with default."""
    dir_path: Path
    if output is None:
        type_str = "Music" if only_audio else "Videos"
        base_dir = Path.home() / type_str
        if base_dir.is_file():
            raise DownloadingError(
                f"File found at default directory (`~/{type_str}`)"
            )
        if not base_dir.exists():
            base_dir.mkdir()
        dir_path = base_dir / sanitize_filename(title)
    elif output.startswith("~"):
        dir_path = Path.home() / output.removeprefix("~")
    else:
        dir_path = Path(output)
        if not dir_path.is_absolute():
            dir_path = Path.cwd() / dir_path
    if dir_path.is_file():
        raise DownloadingError("Output path contains a file")
    if not dir_path.exists():
        dir_path.mkdir(parents=True)
    return dir_path


def fetch_url_raw(url: str) -> bytes:
    res = requests.get(url)
    res.raise_for_status()
    return res.content


def download_mp4(stream: pytube.Stream, dir_path: Path, file_name: str) -> None:
    stream.download(str(dir_path), f"{file_name}.mp4")


def download_mp3(stream: pytube.Stream, dir_path: Path, file_name: str) -> None:
    file_path = dir_path / f"{file_name}.mp3"
    temp_name = "temp_file.mp4"
    temp_path = dir_path / temp_name
    try:
        stream.download(str(dir_path), temp_name)
    except KeyboardInterrupt as e:
        temp_path.unlink(missing_ok=True)
        raise e
    audio = AudioFileClip(str(temp_path))
    audio.write_audiofile(str(file_path), codec="mp3",
                          verbose=False, logger=None)
    temp_path.unlink()


type DownloadFunction = Callable[[pytube.Stream, Path, str], None]
download_functions: dict[str, DownloadFunction] = {
    "mp4": download_mp4,
    "mp3": download_mp3,
}


def download_playlist(playlist_url: str,
                      output: Optional[str],
                      file_type: str,
                      only_audio: bool) -> None:
    """Downloads all videos in a specified YouTube playlist.
    Downloads into `~/Music/<TITLE>/` or `~/Videos/<TITLE>/` by default.

    # Parameters
    ------------
    * `playlist_url`: The URL to the YouTube playlist to be downloaded.
    * `output`: The directory all files will be downloaded into.
    * `only_audio`: Whether video is downloaded.

    # Examples
    ----------
    ```python
    url = input("Enter playlist url: ")
    path = input("Enter output path: ")
    try:
        download_playlist(url, path, "mp4", False)
    except DownloadingError as e:
        print(e.msg)
    else:
        print("Success!")
    ```
    """
    assert file_type in download_functions

    playlist = Playlist(playlist_url)
    dir_path = get_and_validate_dir_path(output, playlist.title, only_audio)
    total_secs = 0
    bytes_downloaded = 0
    vids_downloaded = 0
    total_bytes = 0
    age_restricted_urls: list[str] = []
    print(f"Downloading playlist: {playlist.title}\n")
    for i, vid in enumerate(playlist.videos, start=1):
        stream: Optional[Stream]
        try:
            stream = vid.streams\
                        .filter(file_extension="mp4",
                                only_audio=only_audio)\
                        .first()
        except AgeRestrictedError:
            age_restricted_urls.append(vid.watch_url)
            print("Video is age restricted")
            continue
        if stream is None:
            print("No stream found")
            continue
        if only_audio and not stream.includes_audio_track:
            print("Video has no audio")
            continue
        total_secs += vid.length
        file_name = sanitize_filename(stream.title)
        file_path = dir_path / f"{file_name}.{file_type}"
        if file_path.is_file():
            file_size = file_path.stat().st_size
            total_bytes += file_size
            print(f"Found {i}/{playlist.length}: {stream.title} "
                  f"({format_time(vid.length)})")
            continue
        print(f"Downloading {i}/{playlist.length}: {stream.title} "
              f"({format_time(vid.length)})",
              end="", flush=True)
        cover_data = fetch_url_raw(vid.thumbnail_url)
        metadata = Metadata(title=stream.title,
                            artist=vid.author,
                            cover_data=cover_data)
        try:
            download_functions[file_type](stream, dir_path, file_name)
            if file_type in metadata_functions:
                metadata_functions[file_type](file_path, metadata)
        except KeyboardInterrupt as e:
            file_path.unlink(missing_ok=True)
            print(f"\ndeleted `{str(file_path)}`")
            raise e
        vids_downloaded += 1
        file_size = file_path.stat().st_size
        bytes_downloaded += file_size
        total_bytes += file_size
        print(f" - {format_size(file_size)}")

    print(f"\nFinished downloading playlist: {playlist.title}")
    if vids_downloaded == playlist.length:
        print(f"\tTotal videos: {playlist.length}")
    else:
        print(f"\tDownloaded videos: {vids_downloaded} / {playlist.length}")
    if bytes_downloaded == total_bytes:
        print(f"\tTotal size: {format_size(bytes_downloaded)}")
    else:
        print(f"\tDownloaded size: {format_size(bytes_downloaded)} / "
                                 f"{format_size(total_bytes)}")
    print(f"\tTotal length: {format_time(total_secs, long=True)}")
    print(f"\tDestination: `{str(dir_path)}`")
    if len(age_restricted_urls) != 0:
        print(f"\nAge restricted videos: ({len(age_restricted_urls)})")
        for restricted_url in age_restricted_urls:
            print(f"\t{restricted_url}")


def main() -> None:
    def expect_arg_after(switch: str, i: int) -> None:
        if i == len(sys.argv) - 1:
            print(f"Expected an argument after `{switch}`", file=sys.stderr)
            exit(1)

    playlist_url = None
    output = None
    file_type = "mp4"
    only_audio = False
    args = sys.argv
    i = 1
    while i < len(args):
        match args[i]:
            case "-o":
                expect_arg_after("-o", i)
                i += 1
                output = args[i]
            case "-f":
                expect_arg_after("-f", i)
                i += 1
                file_type = args[i]
            case "-a":
                only_audio = True
            case _:
                if playlist_url is not None:
                    print("Multiple playlist URLs provided", file=sys.stderr)
                    exit(1)
                playlist_url = args[i]
        i += 1
    if file_type in {"mp3"}:
        only_audio = True
    if playlist_url is None:
        print("No playlist URL provided", file=sys.stderr)
        exit(1)
    if file_type not in metadata_functions:
        print(f"Invalid file type `{file_type}`", file=sys.stderr)
        exit(1)
    try:
        download_playlist(
            playlist_url,
            output,
            file_type,
            only_audio,
        )
    except DownloadingError as e:
        print(e.msg, file=sys.stderr)
        exit(1)
    except KeyboardInterrupt:
        print("\nDownload canceled")


if __name__ == "__main__":
    main()
