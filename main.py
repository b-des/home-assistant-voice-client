import asyncio
import audioop
import math
import os
import struct
import time
from threading import Timer
import wave
from collections import deque
from openwakeword.model import Model

import numpy as np
import requests
import pyaudio

CHUNK = 512
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
recorded_wav_path = 'audio.wav'
speech_record_gap = 1
silence_limit = 1
silence_threshold = 1.5  # sec
speech_recognition_server_url = os.getenv('ASSISTANT_ENDPOINT')
rel = RATE / CHUNK
frames = []

slid_window = deque(maxlen=int(silence_limit * rel))

wake_word_detected = False
speech_detected = False
wav_file: wave.Wave_write

p = pyaudio.PyAudio()
info = p.get_host_api_info_by_index(0)
num_devices = info.get('deviceCount')
for i in range(0, num_devices):
    if (p.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
        print("Input Device id ", i, " - ", p.get_device_info_by_host_api_device_index(0, i).get('name'))

stream = p.open(format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                input_device_index=8,
                frames_per_buffer=CHUNK)



async def main():
    global wake_word_detected, speech_detected, wav_file
    false_speech_timer = Timer(5, false_speech_callback)
    finish_speech_timer = Timer(silence_threshold, lambda: print("finish speech"))
    # Timer(0, play_sound, ['sounds/boot.wav']).start()
    while True:
        data = stream.read(CHUNK)
        # data = struct.unpack_from("h" * CHUNK, data)
        # keyword_index = porcupine.process(data)
        frame = np.frombuffer(data, dtype=np.int16)
        prediction = {'alexa': 0}  # model.predict(frame)

        if prediction['alexa'] >= 0.7 and not wake_word_detected:
            print('Wake word detected')
            os.system('pkill -9 aplay')
            wake_word_detected = True
            false_speech_timer = Timer(5, false_speech_callback)
            false_speech_timer.start()
            Timer(0, play_sound, ['sounds/click.wav']).start()
            init_wav()

        if wake_word_detected:
            if wav_file is not None:
                wav_file.writeframes(struct.pack("h" * len(data), *data))

            frame = np.frombuffer(data, dtype=np.int16)
            voice_probability = np.abs(frame).mean()

            if voice_probability > 90:
                false_speech_timer.cancel()
                finish_speech_timer.cancel()
                speech_detected = True
            elif voice_probability < 40 and speech_detected and not finish_speech_timer.is_alive():
                finish_speech_timer = Timer(silence_threshold, finish_speech_callback)
                finish_speech_timer.start()


def init_wav():
    global wav_file
    wav_file = wave.open(recorded_wav_path, "w")
    wav_file.setnchannels(1)
    wav_file.setsampwidth(2)
    wav_file.setframerate(16000)


def false_speech_callback():
    global wake_word_detected
    wake_word_detected = False
    print("Speech was not detected, after 5 seconds")


def finish_speech_callback():
    global wake_word_detected
    global speech_detected
    global wav_file
    print(f'Silence timeout. Speech detected: {speech_detected}')
    wake_word_detected = False

    if wav_file is not None:
        wav_file.close()
        wav_file = None
        if speech_detected:
            request()
    speech_detected = False


def request():
    start = time.time()
    file = {'audio': open(recorded_wav_path, 'rb')}
    r = requests.post(speech_recognition_server_url, files=file, headers={'Accept': '*/*'})
    print(f"Request time: {time.time() - start}")
    start = time.time()
    with open('response.wav', 'wb') as f:
        f.write(r.content)
        print(f"Decode time: {time.time() - start}")
        play_sound('response.wav')


def play_sound(sound_path):
    print(f'Play {sound_path}')
    os.system(f'aplay {sound_path}')


asyncio.run(main())
