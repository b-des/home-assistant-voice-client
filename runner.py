import asyncio
import atexit
import time
from threading import Thread, Event, Timer

import numpy as np
import openwakeword
from pysilero_vad import SileroVoiceActivityDetector
from openwakeword.model import Model

import logger
from config import config

openwakeword.utils.download_models()

MUTE_TIMEOUT = int(config.get('MUTE_TIMEOUT', 0))

log = logger.get(__name__)

class TriggerDetector:
    """
    Reads predictions and detects activations
    This prevents multiple close activations from occurring when
    the predictions look like ...!!!..!!...
    """

    def __init__(self, chunk_size, sensitivity=0.5, trigger_level=3):
        self.chunk_size = chunk_size
        self.sensitivity = sensitivity
        self.trigger_level = trigger_level
        self.activation = 0

    def update(self, prob):
        # type: (float) -> bool
        """Returns whether the new prediction caused an activation"""
        chunk_activated = prob > 1.0 - self.sensitivity

        if chunk_activated or self.activation < 0:
            self.activation += 1
            has_activated = self.activation > self.trigger_level
            if has_activated or chunk_activated and self.activation < 0:
                self.activation = -(8 * 2048) // self.chunk_size

            if has_activated:
                return True
        elif self.activation > 0:
            self.activation -= 1
        return False


class ReadWriteStream(object):
    """
    Class used to support writing binary audio data at any pace,
    optionally chopping when the buffer gets too large
    """

    def __init__(self, s=b'', chop_samples=-1):
        self.buffer = s
        self.write_event = Event()
        self.chop_samples = chop_samples

    def __len__(self):
        return len(self.buffer)

    def read(self, n=-1, timeout=None):
        if n == -1:
            n = len(self.buffer)
        if 0 < self.chop_samples < len(self.buffer):
            samples_left = len(self.buffer) % self.chop_samples
            self.buffer = self.buffer[-samples_left:]
        return_time = 1e10 if timeout is None else (
                timeout + time.time()
        )
        while len(self.buffer) < n:
            self.write_event.clear()
            if not self.write_event.wait(return_time - time.time()):
                return b''
        chunk = self.buffer[:n]
        self.buffer = self.buffer[n:]
        return chunk

    def write(self, s):
        self.buffer += s
        self.write_event.set()

    def flush(self):
        """Makes compatible with sys.stdout"""
        pass


class InfiniteLoopThread(Thread):
    def __init__(self, group=None, target=None, name=None,
                 args=(), kwargs=None, *, daemon=None):
        super().__init__(group, target, name, args, kwargs, daemon=daemon)
        self.loop = None
        self.running = True

    def run(self):
        # Create and set the event loop for the thread
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def stop(self):
        # Stop the event loop safely
        self.running = False
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)

    def add_task(self, coro):
        # Add a coroutine task to the event loop
        return asyncio.run_coroutine_threadsafe(coro, self.loop)


class PreciseRunner(object):
    """
    Wrapper to use Precise. Example:
    >>> def on_act():
    ...     print('Activation!')
    ...
    >>> p = PreciseRunner(PreciseEngine('./precise-engine'), on_activation=on_act)
    >>> p.start()
    >>> from time import sleep; sleep(10)
    >>> p.stop()

    Args:
        engine (Engine): Object containing info on the binary engine
        trigger_level (int): Number of chunk activations needed to trigger on_activation
                       Higher values add latency but reduce false positives
        sensitivity (float): From 0.0 to 1.0, how sensitive the network should be
        stream (BinaryIO): Binary audio stream to read 16000 Hz 1 channel int16
                           audio from. If not given, the microphone is used
        on_prediction (Callable): callback for every new prediction
        on_activation (Callable): callback for when the wake word is heard
    """

    SILENCE_DELAY_THRESHOLD = 1
    WAIT_FOR_SPEECH_DURATION = 4

    def __init__(self, trigger_level=3, sensitivity=0.5, stream=None,
                 on_prediction=lambda x: None,
                 on_finish_phrase=lambda x, y: None,
                 on_activation=lambda: None,
                 on_listen_phrase=lambda x: None):
        self.speech_detected = False
        self.wake_word_detected = False
        self.trigger_level = trigger_level
        self.stream = stream
        self.on_prediction = on_prediction
        self.on_activation = on_activation
        self.on_listen_phrase = on_listen_phrase
        self.on_finish_phrase = on_finish_phrase
        self.chunk_size = 1024
        self.speech = bytearray()
        self.wake_word = config.get('WAKE_WORD_MODEL')
        self.wakewords = [
            # 'models/Mahvareek.tflite',
            # 'models/ahtlahz.onnx',
            # 'models/ahtl_us.onnx',

            f'models/{self.wake_word}.tflite',
        ]
        self.model = Model(self.wakewords, inference_framework='tflite')
        self.pa = None
        self.thread = None
        self.running = False
        self.is_paused = False

        self.vad_model = SileroVoiceActivityDetector()
        self.detector = TriggerDetector(self.chunk_size, sensitivity, trigger_level)
        self.false_speech_timer = Timer(self.WAIT_FOR_SPEECH_DURATION, self.false_speech_callback)
        self.finish_speech_timer = Timer(self.SILENCE_DELAY_THRESHOLD, lambda: print("finish speech"))
        atexit.register(self.stop)

    def wake_up(self, timeout=WAIT_FOR_SPEECH_DURATION):
        self.wake_word_detected = True
        self.false_speech_timer = Timer(timeout, self.false_speech_callback)
        self.false_speech_timer.start()

    def mute(self, timeout=MUTE_TIMEOUT):
        log.info(f'Mute mic for {timeout} seconds')
        self.is_paused = True
        if timeout > 0:
            Timer(timeout, self.un_mute).start()

    def un_mute(self):
        log.info('Unmute mic')
        self.is_paused = False

    def false_speech_callback(self):
        self.on_finish_phrase(self.speech_detected, None)
        self.wake_word_detected = False
        self.speech.clear()

    def finish_speech_callback(self):
        self.on_finish_phrase(self.speech_detected, self.speech)
        self.wake_word_detected = False
        self.speech_detected = False
        self.speech.clear()

    def _wrap_stream_read(self, stream):
        """
        pyaudio.Stream.read takes samples as n, not bytes
        so read(n) should be read(n // sample_depth)
        """
        import pyaudio
        if getattr(stream.read, '__func__', None) is pyaudio.Stream.read:
            stream.read = lambda x: pyaudio.Stream.read(stream, x // 2, False)

    async def start(self):
        """Start listening from stream"""
        if self.stream is None:
            from pyaudio import PyAudio, paInt16
            self.pa = PyAudio()
            self.stream = self.pa.open(
                16000,
                1,
                paInt16,
                True,
                False,
                int(config.get('SOUND_DEVICE_INDEX', 0)),
                frames_per_buffer=self.chunk_size
            )

        self._wrap_stream_read(self.stream)

        self.running = True
        self.is_paused = False
        self.thread = Thread(target=self._handle_predictions, daemon=True)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        """Stop listening and close stream"""
        if self.thread:
            self.running = False
            if isinstance(self.stream, ReadWriteStream):
                self.stream.write(b'\0' * self.chunk_size)
            self.thread.join()
            self.thread = None

        if self.pa:
            self.pa.terminate()
            self.stream.stop_stream()
            self.stream = self.pa = None

    def pause(self):
        self.is_paused = True

    def play(self):
        self.is_paused = False

    def _wake_word_detected(self, frame):
        prediction = self.model.predict(frame)

        if prediction[self.wake_word] >= 0.6:
            print(f'Activation without update: {prediction}')
        activated = self.detector.update(prediction[self.wake_word])
        if activated:
            print(f'Activation with update: {prediction}')
        return activated and not self.wake_word_detected

    def _handle_predictions(self):
        """Continuously check Precise process output"""
        while self.running:
            if self.is_paused:
                continue

            chunk = self.stream.read(self.chunk_size)
            frame = np.frombuffer(chunk, dtype=np.int16)
            if self._wake_word_detected(frame):
                self.wake_up()
                self.on_activation()

            if self.wake_word_detected:
                self.on_listen_phrase(chunk)
                self.speech.extend(chunk)
                voice_probability = self.vad_model(chunk)

                if voice_probability > 0.5:
                    self.false_speech_timer.cancel()
                    self.finish_speech_timer.cancel()
                    self.speech_detected = True
                elif voice_probability < 0.4 and self.speech_detected and not self.finish_speech_timer.is_alive():
                    self.finish_speech_timer = Timer(self.SILENCE_DELAY_THRESHOLD, self.finish_speech_callback)
                    self.finish_speech_timer.start()
