from time import sleep, time
import zmq
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers import BlenderbotTokenizer, BlenderbotForConditionalGeneration
import torch


def listen_for_speech(sock):
    """ This is designed to block. For now, this bot is turn based"""
    sock.send(b"LISTEN_ONCE")
    msg = sock.recv()
    captured_speech = eval(msg.decode())["text"]
    return captured_speech


def speak_text(text: str, sock):
    """ This is designed to block. For now, this bot is turn based """
    sock.send(bytearray(text, 'utf8'))
    msg = sock.recv()
    return


class DialogueGPTAgent:

    def __init__(self, starting_message: str):
        # TODO figure out how to cache these
        self.tokenizer = AutoTokenizer.from_pretrained("microsoft/DialoGPT-medium")
        self.model = AutoModelForCausalLM.from_pretrained("microsoft/DialoGPT-medium")
        self.chat_history_ids = self.tokenizer.encode(starting_message + self.tokenizer.eos_token, return_tensors='pt')

    def get_response(self, new_query: str):
        # encode the new user input, add the eos_token and return a tensor in Pytorch
        new_user_input_ids = self.tokenizer.encode(new_query + self.tokenizer.eos_token, return_tensors='pt')

        # append the new user input tokens to the chat history
        bot_input_ids = torch.cat([self.chat_history_ids, new_user_input_ids], dim=-1)

        # generated a response while limiting the total chat history to 1000 tokens,
        self.chat_history_ids = self.model.generate(bot_input_ids, min_length=25, max_length=1000,
                                                    pad_token_id=self.tokenizer.eos_token_id,
                                                    no_repeat_ngram_size=3,
                                                    do_sample=True, top_p=0.95)

        reply = self.tokenizer.decode(self.chat_history_ids[:, bot_input_ids.shape[-1]:][0],
                                      skip_special_tokens=True)

        return reply


class BlenderBotAgent:
    """ This is the default as it works better (IMHO)"""

    def __init__(self):
        self.use_cuda = torch.cuda.is_available()
        # Note: you can try the 1 Billion distillation of BlenderBot as well: facebook/blenderbot-1B-distill
        self.tokenizer = BlenderbotTokenizer.from_pretrained("facebook/blenderbot-400M-distill")
        self.model = BlenderbotForConditionalGeneration.from_pretrained("facebook/blenderbot-400M-distill")
        if self.use_cuda:
            self.model = self.model.to("cuda")

    def get_response(self, query: str):

        inputs = self.tokenizer.encode(query + self.tokenizer.eos_token, return_tensors='pt')
        if self.use_cuda:
            inputs = inputs.to("cuda")

        reply_ids = self.model.generate(inputs, min_length=25, max_length=500,
                                        pad_token_id=self.tokenizer.eos_token_id,
                                        do_sample=True, top_p=0.95, temperature=1.2)

        print(len(reply_ids[0]))
        reply = self.tokenizer.decode(reply_ids[0], skip_special_tokens=True)

        return reply


def control_main(port_config=None, dialogue_config=None):
    if port_config is None:
        port_config = {"system_sync_port": 5553,  # report for system to check that modules are synced properly
                       "pub_to_proxy_port": 5554,  # port to publish to proxy so in the proxy it is xsub
                       "sub_to_proxy_port": 5555,  # port to subscribe to the proxy so in the proxy it is xpub
                       "stt_req_rep_port": 5556,  # REQ-REP control port for the stt pub sub
                       "tts_req_rep_port": 5557,  # REQ-REP port for the text to speech
                       }

    chatbot_model = "BlenderBot"

    # TODO: implement the optional input of the dialogue config
    if dialogue_config is None:
        hello_message = "Hello! My name is Rose. How are you today? What would you like to talk about?"
        shutdown_commands = ["go to sleep rose", "good night rose", "goodnight rose", "good bye rose",
                             "goodbye rose", "sweet dreams rose"]

    # ------------------------------------------------------------------------------------------------------------------
    # define the contexts and sockets of main control process
    context = zmq.Context()
    sockets_list = []

    # reply socket to system
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
    socket_subscriber.setsockopt(zmq.SUBSCRIBE, b"SPEECH_TO_TEXT")
    sockets_list.append(socket_subscriber)

    # # # open stt socket
    socket_speech_to_text = context.socket(zmq.REQ)
    socket_speech_to_text.connect("tcp://localhost:{}".format(port_config["stt_req_rep_port"]))
    #
    # # open tts socket:
    socket_text_to_speech = context.socket(zmq.REQ)
    socket_text_to_speech.connect("tcp://localhost:{}".format(port_config["tts_req_rep_port"]))

    # make the poller.
    # NOTE: this doesn't include the speech to text and text to speech sockets as they are intended to be blocking
    poller = zmq.Poller()
    poller.register(socket_system_sync, zmq.POLLIN)
    poller.register(socket_subscriber, zmq.POLLIN)

    # ------------------------------------------------------------------------------------------------------------------
    # make the agent class instance
    if chatbot_model == 'DialogueGPT':
        agent = DialogueGPTAgent(hello_message)
    else:
        agent = BlenderBotAgent()

    # ------------------------------------------------------------------------------------------------------------------
    # inform the system that we have connected all sockets and are ready to go
    socket_system_sync.send(b"CONTROL MODULE")
    msg = socket_system_sync.recv()  # this one can be blocking

    # ------------------------------------------------------------------------------------------------------------------
    t_sleep = 0.1

    # Now wait for the System to tell us that all modules have connected their sockets and we can start running things
    while True:
        topic, msg = socket_subscriber.recv_multipart()
        if topic == b"SYSTEM" and msg == b"START":
            break
        else:
            sleep(t_sleep)
    sleep(t_sleep)

    # ------------------------------------------------------------------------------------------------------------------
    # now start actual running of the system

    # send hello message
    speak_text(hello_message, socket_text_to_speech)
    sleep(t_sleep)

    # and loop over waiting for speech, sending it to the agent and speaking the response
    while True:

        # listen for speech
        captured_speech = listen_for_speech(socket_speech_to_text)
        print(captured_speech)

        # TODO: The shutdown message should be configurable as well
        if captured_speech in shutdown_commands:
            speak_text("I'm going to sleep now. Let's talk more soon.", socket_text_to_speech)
            socket_publisher.send_multipart([b"CONTROL", b"SHUTDOWN"])
            break

        # ask the agent what to say in return
        text_to_speak = agent.get_response(captured_speech)

        # speak the response
        speak_text(text_to_speak, socket_text_to_speech)
        sleep(t_sleep)


if __name__ == "__main__":
    control_main()
