import subprocess
import pyaudio


class Audio(object):
    """Streams raw audio from microphone. Data is received in a separate thread, and stored in a buffer, to be read from."""
    FORMAT = pyaudio.paInt16
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
        self.stream.write(frames)

    def play_file_async(self, file):
        try:
            subprocess.Popen(["aplay", file])
        except Exception as e:
            print(f"Error playing sound: {e}")

    def play_file(self, file):
        try:
            subprocess.run(["aplay", file], check=True)
        except Exception as e:
            print(f"Error playing sound: {e}")

    def close(self):
        # self.stream.stop_stream()
        self.stream.close()
        self.pa.terminate()
