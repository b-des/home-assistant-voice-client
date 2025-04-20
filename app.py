import asyncio

from audio import Audio
from client import Client
from commands import Command
from runner import PreciseRunner
from config import config

main_loop = asyncio.get_event_loop()
audio = Audio()
client = Client(config.get('ZEROMQ_HOST'), config.get('NAME'))


def on_activation():
    audio.play_file_async('sounds/click.wav')
    asyncio.run_coroutine_threadsafe(client.send(Command.START_SPEAK.value, b''), main_loop)


def on_listen_phrase(chunk):
    # print('on_listen_phrase')
    asyncio.run_coroutine_threadsafe(client.send(Command.CONTINUE.value, chunk), main_loop)


def on_finish_phrase(speech_detected, data):
    print(f'speech_detected: {speech_detected}')
    if speech_detected:
        asyncio.run_coroutine_threadsafe(client.send(Command.FINISH.value, b''), main_loop)
    else:
        asyncio.run_coroutine_threadsafe(client.send(Command.CANCEL.value, b''), main_loop)


def on_receive_data(tag, params, frame):
    print(tag)
    print(params)
    if tag == 'SPEAK':
        audio.play(frame)

    if tag == 'INIT_CONVERSATION':
        audio.play_file('sounds/init.mp3')

    if tag == 'WAKEUP':
        runner.wake_up(params['wait_timeout'])


runner = PreciseRunner(sensitivity=0.8,
                       on_activation=on_activation,
                       on_listen_phrase=on_listen_phrase,
                       on_finish_phrase=on_finish_phrase)

if __name__ == "__main__":
    # asyncio.run(App().run())

    # p.force_wake_up()
    # tasks = [asyncio.create_task(coroutine) for coroutine in [client.run(None), runner.start()]]

    audio.play_file('sounds/boot.wav')
    main_loop.run_until_complete(asyncio.gather(client.run(on_receive_data), runner.start()))
    try:
        print("[main] Starting asyncio event loop")
        main_loop.run_forever()
    except KeyboardInterrupt:
        print("[main] Stopping")
    finally:
        main_loop.stop()

# async def main() -> None:
#     app = App()
#     tasks = [asyncio.create_task(coroutine) for coroutine in [app.run(), app.client.run(app.test())]]
#     await asyncio.wait(tasks)
#
#
# if __name__ == "__main__":
#     asyncio.run(main())
