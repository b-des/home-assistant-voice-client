from threading import Timer

import pyaudio
from playsound import playsound


class Audio(object):
    """Streams raw audio from microphone. Data is received in a separate thread, and stored in a buffer, to be read from."""

    FORMAT = pyaudio.paInt16
    # Network/VAD rate-space
    RATE_PROCESS = 16000
    CHANNELS = 1
    BLOCKS_PER_SECOND = 50

    def __init__(self):
        self.pa = pyaudio.PyAudio()
        info = self.pa.get_host_api_info_by_index(0)
        num_devices = info.get('deviceCount')
        for i in range(0, num_devices):
            if (self.pa.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
                print("Input Device id ", i, " - ", self.pa.get_device_info_by_host_api_device_index(0, i).get('name'))

        self.stream = self.pa.open(format=self.pa.get_format_from_width(2),
                                   channels=1,
                                   rate=16000,
                                   output=True,
                                   frames_per_buffer=1024)

    def play(self, frames):
        # playsound(filename)
        self.stream.write(frames)

    def play_file_async(self, file):
        Timer(0, playsound, [file]).start()

    def play_file(self, file):
        playsound(file)

    # with wave.open(file, 'rb') as f:
    #     width = f.getsampwidth()
    #     channels = f.getnchannels()
    #     rate = f.getframerate()
    #     frames = f.readframes(1024)
    #     self.stream.write(frames)
    #     while frames != '':
    #         self.stream.write(frames)
    #         frames = f.readframes(11024)

    def _play(self, file):
        playsound(file)

    def close(self):
        # self.stream.stop_stream()
        self.stream.close()
        self.pa.terminate()
