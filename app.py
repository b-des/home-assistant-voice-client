import asyncio
import threading

from audio import Audio
from client import Client
from commands import Command
from runner import PreciseRunner
from config import config
from udp_discovery import udp_listener, udp_broadcast

main_loop = asyncio.get_event_loop()
audio = Audio()
client = Client(config.get('ZEROMQ_ROUTER_HOST'), config.get('NAME'))


def on_activation():
    asyncio.run_coroutine_threadsafe(client.publish('request mute'), main_loop)
    audio.play_file_async('sounds/click.wav')
    asyncio.run_coroutine_threadsafe(client.send(Command.START_SPEAK.value, b''), main_loop)


def on_listen_phrase(chunk):
    # print('on_listen_phrase')
    asyncio.run_coroutine_threadsafe(client.send(Command.CONTINUE.value, chunk), main_loop)


def on_finish_phrase(speech_detected, data):
    print(f'speech_detected: {speech_detected}')
    asyncio.run_coroutine_threadsafe(client.publish('request unmute'), main_loop)
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


def on_peer_message(message):
    if message == 'mute':
        runner.mute()
    if message == 'unmute':
        runner.un_mute()


queue = asyncio.Queue()


async def udp_consumer():
    while True:
        msg = await queue.get()
        print(f'Message from queue: {msg}')
        await client.subscribe(msg)


runner = PreciseRunner(sensitivity=0.8,
                       on_activation=on_activation,
                       on_listen_phrase=on_listen_phrase,
                       on_finish_phrase=on_finish_phrase)

if __name__ == "__main__":
    # asyncio.run(App().run())

    # p.force_wake_up()
    # tasks = [asyncio.create_task(coroutine) for coroutine in [client.run(None), runner.start()]]
    audio.play_file('sounds/boot.wav')
    threading.Thread(target=udp_listener, args=(main_loop, queue), daemon=True).start()
    threading.Thread(target=udp_broadcast, daemon=True).start()
    main_loop.run_until_complete(
        asyncio.gather(client.start(on_receive_data, on_peer_message), runner.start(), udp_consumer()))
    try:
        print("[main] Starting asyncio event loop")
        main_loop.run_forever()
    except KeyboardInterrupt:
        print("[main] Stopping")
    finally:
        runner.stop()
        audio.close()
        main_loop.stop()

# async def main() -> None:
#     app = App()
#     tasks = [asyncio.create_task(coroutine) for coroutine in [app.run(), app.client.run(app.test())]]
#     await asyncio.wait(tasks)
#
#
# if __name__ == "__main__":
#     asyncio.run(main())
