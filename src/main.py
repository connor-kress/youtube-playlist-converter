from pytube import YouTube


def main() -> None:
    yt = YouTube("https://www.youtube.com/watch?v=CNjqpg-G1xE")
    stream = yt.streams\
               .filter(only_audio=True, file_extension="mp4")\
               .first()
    if stream is None:
        print("No stream found")
        return
    stream.download("data", "song.mp4")
    print("Done")


if __name__ == "__main__":
    main()
