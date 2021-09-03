from time import sleep
import pyaudio
from vosk import Model, KaldiRecognizer
import zmq

# DIRECTORY WHERE THE VOSK SPEECH TO TEXT MODEL IS LOCATED
pwd_vosk_model = "../models/vosk-model-en-us-aspire-0.2"

class VoiceCapture:

    def __init__(self, pwd_model=pwd_vosk_model):
        """Class that will set up a Vosk speech to text instance, start and stop pyaudio streams and listen for speech

        :param pwd_model: full path to vosk model
        """
        # initialize the model and the recognizer
        self.model = Model(pwd_model)
        self.recognizer = KaldiRecognizer(self.model, 16000)

        # define audio stream but don't start it yet
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=8000)
        self.is_listening = False
        self.stream.stop_stream()

    def start_audio_stream(self):
        """restart the pyaudio stream """
        self.stream.start_stream()
        self.is_listening = True

    def stop_audio_stream(self):
        """pause the pyaudio stream"""
        self.stream.stop_stream()
        self.is_listening = False

    def shut_down_pyaudio(self):
        """ shut down the pyaudio stream"""
        self.stream.close()
        self.p.terminate()

    def listen_once(self):
        """listen for text and return it"""
        # TODO We may want to implement a time out and return a None in that case.
        done_listening = False
        self.start_audio_stream()
        while not done_listening:
            audio_data = self.stream.read(4000)
            if len(audio_data) == 0:
                result = None
                break
            if self.recognizer.AcceptWaveform(audio_data):
                result_text = self.recognizer.Result()
                if eval(result_text)["text"] != "":
                    done_listening = True
        self.stop_audio_stream()
        return result_text


def speech_to_text_main(port_config=None):
    if port_config is None:
        port_config = {"system_sync_port": 5553,  # report for system to check that modules are sync'ed properly
                       "pub_to_proxy_port": 5554,  # port to publish to proxy so in the proxy it is xsub
                       "sub_to_proxy_port": 5555,  # port to subscribe to the proxy so in the proxy it is xpub
                       "stt_req_rep_port": 5556,  # REQ-REP control port for the stt pub sub
                       "tts_req_rep_port": 5557,  # REQ-REP port for the text to speech
                       }

    t_sleep = 0.1

    # ------------------------------------------------------------------------------------------------------------------
    # Create zmq context and sockets

    context = zmq.Context()
    sockets_list = []

    # system sync socket - this is for informing system of status
    socket_system_sync = context.socket(zmq.REQ)
    socket_system_sync.connect("tcp://localhost:{}".format(port_config["system_sync_port"]))
    sockets_list.append(socket_system_sync)

    # publishing socket
    socket_publisher = context.socket(zmq.PUB)
    socket_publisher.connect("tcp://localhost:{}".format(port_config["pub_to_proxy_port"]))
    sockets_list.append(socket_publisher)

    # subscribing socket
    socket_subscriber = context.socket(zmq.SUB)
    socket_subscriber.connect("tcp://localhost:{}".format(port_config["sub_to_proxy_port"]))
    socket_subscriber.setsockopt(zmq.SUBSCRIBE, b"SYSTEM")
    sockets_list.append(socket_subscriber)

    # speech to text control socket - this is for receiving a request for text and replying
    socket_stt_reply = context.socket(zmq.REP)
    socket_stt_reply.bind("tcp://*:{}".format(port_config["stt_req_rep_port"]))

    # make poller because we are listening to both the subscriber and the stt_reply sockets
    poller = zmq.Poller()
    poller.register(socket_subscriber, zmq.POLLIN)
    poller.register(socket_stt_reply, zmq.POLLIN)

    # ------------------------------------------------------------------------------------------------------------------
    # initialize voice capture class
    vcap = VoiceCapture()

    # ------------------------------------------------------------------------------------------------------------------
    # inform the system that we have connected all sockets and are ready to listen for speech
    socket_system_sync.send(b"TEXT TO SPEECH MODULE")
    msg = socket_system_sync.recv()  # this one can be blocking

    # ------------------------------------------------------------------------------------------------------------------
    # Main Loop
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
            elif socket_stt_reply in socks and socks[socket_stt_reply] == zmq.POLLIN:
                msg = socket_stt_reply.recv()
                if msg == b"LISTEN_ONCE":
                    captured_speech = vcap.listen_once()
                    # TODO Think about whether we want to deal with low confidence words by treating as masked text problem
                    # TODO or more simply that we have some confidence threshold below which we ask for user to repeat themselves.
                    socket_stt_reply.send(bytearray(captured_speech, 'utf8'))

        except KeyboardInterrupt:
            break

        sleep(t_sleep)

    # for shutting down softly
    print("shutting everything down")
    for sock in sockets_list:
        sock.close()
    context.term()


if __name__ == "__main__":
    speech_to_text_main()
