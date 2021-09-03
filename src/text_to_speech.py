import zmq
import simpleaudio as sa
import os
from time import sleep

# ----------------------------------------------------------------------------------------------------------------------
# A few ways of playing .wav files ... comment these out but keep for reference

# import pyaudio
# import wave
# from pydub import AudioSegment
# from pydub.playback import play

# def play_pydub(wavefile: str):
#     silent_segment = AudioSegment.silent(duration=1000)
#     speech = AudioSegment.from_wav(wavefile)
#     final_speech = silent_segment + speech
#     play(final_speech)
#
#
# def play_wave(wavefile: str):
#     CHUNK = 1024
#
#     wf = wave.open(wavefile, 'rb')
#
#     # instantiate PyAudio (1)
#     p = pyaudio.PyAudio()
#
#     # open stream (2)
#     stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
#                     channels=wf.getnchannels(),
#                     rate=wf.getframerate(),
#                     output=True)
#
#     # read data
#     data = wf.readframes(CHUNK)
#
#     # play stream (3)
#     while len(data) > 0:
#         stream.write(data)
#         data = wf.readframes(CHUNK)
#
#     # stop stream (4)
#     stream.stop_stream()
#     stream.close()
#
#     # close PyAudio (5)
#     p.terminate()


def talk_pico2wave(text: str, tmp_file="tmp.wav"):
    """ This is very hacky. I don't like writing a file, playing it and then deleting ...
    but, the pico2speaker command seems to be defunct and so I'm stuck with pico2wave"""
    text = "  ...  " + text
    # write speech to a .wav file
    pico_command = 'pico2wave -w ' + tmp_file + ' -l en-GB "' + text + ' "'
    print(pico_command)
    os.system(pico_command)  # this blocks

    # play .wav file using simple audio
    # simple audio
    wave_obj = sa.WaveObject.from_wave_file(tmp_file)
    play_obj = wave_obj.play()
    play_obj.wait_done()  # Wait until sound has finished playing
    print("done speaking")

    # delete .wav file (clean up)
    rm_command = 'rm ' + tmp_file
    os.system(rm_command)


def text_to_speech_main(port_config=None):
    """The intended functionality here is to speak only one response at a time. Specifically
    receive text as a zmq message, speak it, and then reply with a message that the text has been
    spoken. As such, this function is deliberately blocking.

    In between we listen for system commands if needed."""

    if port_config is None:
        port_config = {"system_sync_port": 5553,  # report for system to check that modules are sync'ed properly
                       "pub_to_proxy_port": 5554,  # port to publish to proxy so in the proxy it is xsub
                       "sub_to_proxy_port": 5555,  # port to subscribe to the proxy so in the proxy it is xpub
                       "stt_req_rep_port": 5556,  # REQ-REP control port for the stt pub sub
                       "tts_req_rep_port": 5557,  # REQ-REP port for the text to speech
                       }

    t_sleep = 0.1

    # ------------------------------------------------------------------------------------------------------------------
    # Make context and sockets

    context = zmq.Context()
    sockets_list = []

    # system sync socket
    socket_system_sync = context.socket(zmq.REQ)
    socket_system_sync.connect("tcp://localhost:{}".format(port_config["system_sync_port"]))
    sockets_list.append(socket_system_sync)

    # socket for publishing to proxy
    socket_publisher = context.socket(zmq.PUB)
    socket_publisher.connect("tcp://localhost:{}".format(port_config["pub_to_proxy_port"]))
    sockets_list.append(socket_publisher)

    # socket for subscribing to proxy
    socket_subscriber = context.socket(zmq.SUB)
    socket_subscriber.connect("tcp://localhost:{}".format(port_config["sub_to_proxy_port"]))
    socket_subscriber.setsockopt(zmq.SUBSCRIBE, b"SYSTEM")
    sockets_list.append(socket_subscriber)

    # open tts_reply socket
    socket_tts_reply = context.socket(zmq.REP)
    socket_tts_reply.bind("tcp://*:{}".format(port_config["tts_req_rep_port"]))
    sockets_list.append(socket_tts_reply)

    # make poller because we are listening to both the subscriber and the stt_reply sockets
    poller = zmq.Poller()
    poller.register(socket_subscriber, zmq.POLLIN)
    poller.register(socket_tts_reply, zmq.POLLIN)

    # ------------------------------------------------------------------------------------------------------------------
    # inform the system that we have connected all sockets and are ready to go
    socket_system_sync.send(b"SPEECH TO TEXT MODULE")
    msg = socket_system_sync.recv()  # this one can be blocking

    # ------------------------------------------------------------------------------------------------------------------
    # main loop
    while True:

        try:
            socks = dict(poller.poll(100))  # poll for .1 ms don't block

            # if a message from the system
            if socket_subscriber in socks and socks[socket_subscriber] == zmq.POLLIN:
                topic, message = socket_subscriber.recv_multipart()
                print(topic.decode(), message.decode())
                if message == b"SHUTDOWN":
                    break

            # if a request to listen for speech
            elif socket_tts_reply in socks and socks[socket_tts_reply] == zmq.POLLIN:
                text = socket_tts_reply.recv().decode()
                talk_pico2wave(text)
                sleep(t_sleep)
                socket_tts_reply.send(b"text spoken")

        except KeyboardInterrupt:
            break

        sleep(t_sleep)


if __name__ == "__main__":
    text_to_speech_main()
