import os
import sys
import re
from pathlib import Path
import requests
import zipfile

sys.path.insert(0, str(Path("./ffmpeg/").absolute()) + os.path.sep)

import ffmpeg


class Converter:
    time_calculation = "stream"  # "xml" or "stream"

    def __init__(self, meeting_folder: str, output_folder: str = "./output/", fps: int = 10, debug=False):
        self.log_level = "info" if debug else "quiet"
        self.fps = fps
        self.meeting_folder = Path(meeting_folder)
        self.output_folder = Path(output_folder)
        if not self.output_folder.exists():
            self.output_folder.mkdir(parents=True)
        self.output_file_name = self.meeting_folder.stem
        main_stream = (self.meeting_folder / "mainstream.xml").read_text()
        self.main_stream = main_stream
        self.start_time = self.get_xml_time(main_stream)

    @staticmethod
    def get_xml_time(xml_text: str):
        start_time = re.findall(r"(\d+):(\d+):(\d+)", xml_text)[0]
        start_time = int(start_time[0]) * 3600 + int(start_time[1]) * 60 + int(start_time[2])
        start_time *= 1000
        return start_time

    @staticmethod
    def get_video_duration(video_file):
        if isinstance(video_file, Path):
            video_file = str(video_file)
        return int(float(ffmpeg.probe(video_file)['format']['duration']) * 1000)

    def get_time(self, file_name: str):
        matches = re.finditer(r"{}".format(file_name), self.main_stream)
        name_locations = []
        for match in matches:
            start, end = match.span()
            name_locations.append(start)

        matches = re.finditer(r'time="(\d+)"'.format(file_name), self.main_stream)
        start_time = 0
        end_time = 0
        for m in matches:
            if m.span()[0] < name_locations[0]:
                start_time = int(m.group(1))

            if m.span()[0] > name_locations[-1]:
                end_time = int(m.group(1))
                break
        return start_time, end_time

    def concat_audios(self):
        voip_files = self.meeting_folder.glob("cameraVoip*.flv")
        audios = []
        for voip_file in voip_files:
            prop = ffmpeg.probe(str(voip_file), select_streams='a')

            if prop['streams']:
                aud = ffmpeg.input(str(voip_file)).audio
                if self.time_calculation == "xml":
                    start_time = self.get_xml_time(
                        open(str(voip_file).replace(".flv", ".xml")).read()
                    ) - self.start_time
                else:
                    start_time = self.get_time(voip_file.stem)[0]
                audios.append(ffmpeg.filter(aud, 'adelay', '{}ms'.format(start_time)))

        if len(audios) > 1:
            aud_out = ffmpeg.filter(audios, 'amix', inputs=len(audios))
        else:
            aud_out = audios[0]

        return aud_out

    def concat_videos(self):
        video_files = self.meeting_folder.glob("screenshare*.flv")
        videos = []
        end_of_prev_video = 0
        for video_file in video_files:
            if not Path(str(video_file).replace(".flv", ".mp4")).exists():
                vid = ffmpeg.input(str(video_file)).video
                ffmpeg.run(ffmpeg.output(vid, str(video_file).replace(".flv", ".mp4"), r=self.fps,
                                         loglevel=self.log_level), overwrite_output=True)
            vid = ffmpeg.input(str(video_file).replace(".flv", ".mp4")).video
            if self.time_calculation == "xml":
                video_duration = self.get_video_duration(str(video_file).replace(".flv", ".mp4"))
                start_time = self.get_xml_time(open(str(video_file).replace(".flv", ".xml")).read()) - self.start_time
                end_time = start_time + video_duration
            else:
                start_time, end_time = self.get_time(video_file.stem)
            videos.append(ffmpeg.filter(vid, 'tpad', start_duration='{}ms'.format(start_time - end_of_prev_video)))
            end_of_prev_video = end_time

        if len(videos) == 0:
            vid_out = None
        elif len(videos) == 1:
            vid_out = videos[0]
        else:
            vid_out = ffmpeg.filter(videos, 'concat', n=str(len(videos)), v=1, a=0)
        return vid_out

    def convert_meeting(self):
        aud_out = self.concat_audios()
        vid_out = self.concat_videos()
        ffmpeg_concat = ffmpeg.concat(vid_out, aud_out, v=1, a=1)
        ffmpeg_output = ffmpeg_concat.output(str(self.output_folder / (self.output_file_name + '.mp4')),
                                             loglevel=self.log_level)
        ffmpeg_output.run(overwrite_output=True)


class Downloader:
    def __init__(self, url, output_file):
        self.url = url
        self.output_file = Path(output_file)
        self.session = requests.Session()

    def download(self):
        url, output_file = self.url, self.output_file
        response = self.session.get(url)
        if response.status_code != 200:
            raise Exception("Login failed")
        url = '/'.join(url.split("/")[:-1]) + '/output/' + output_file.stem + ".zip?download=zip"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        response = self.session.get(url, stream=True)
        with output_file.open("wb") as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
                    f.flush()
        return True

    def unzip(self):
        output_folder = self.output_file.parent / self.output_file.stem
        if not output_folder.exists():
            output_folder.mkdir(parents=True)
        with zipfile.ZipFile(self.output_file, 'r') as zip_ref:
            zip_ref.extractall(output_folder)
        return output_folder
