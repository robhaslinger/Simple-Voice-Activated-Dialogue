from time import sleep, time
import zmq
import multiprocessing as mp
from speech_to_text import speech_to_text_main
from dialogue_control import control_main
from text_to_speech import text_to_speech_main


def start_pubsub_proxy(port_config):
    """ This is the pubsub proxy. We start it in another process as it blocks until we kill it"""

    # create the zmq proxy. This must be started in it's own thread or process or it will block
    context_proxy = zmq.Context()

    # socket that others publish to
    publish_to_socket = context_proxy.socket(zmq.XSUB)
    publish_to_socket.bind("tcp://*:{}".format(port_config["pub_to_proxy_port"]))

    # socket that others subscribe to
    subscribe_to_socket = context_proxy.socket(zmq.XPUB)
    subscribe_to_socket.bind("tcp://*:{}".format(port_config["sub_to_proxy_port"]))

    # now start the proxy
    zmq.proxy(publish_to_socket, subscribe_to_socket)


def start_all_processes(process_funcs, port_config):
    """ Starts up processes"""
    # empty list for storing processes
    process_list = []

    # start processes
    for pf in process_funcs:
        # start speech to text process
        new_process = mp.Process(target=pf, kwargs={"port_config": port_config})
        new_process.start()
        process_list.append(new_process)

    return process_list


def stop_all_processes(process_list):
    """Terminates all processes"""
    for p in process_list:
        print("terminating process", p)
        p.terminate()


def run_main(port_config=None):
    """ This is responsible for starting up the system and shutting it down, either due to keyboard interrupt or the
    system itself shutting down"""

    t_sleep = 0.1

    # set default ports
    if port_config is None:
        port_config = {"system_sync_port": 5553,  # report for system to check that modules are sync'ed properly
                       "pub_to_proxy_port": 5554,  # port to publish to proxy so in the proxy it is xsub
                       "sub_to_proxy_port": 5555,  # port to subscribe to the proxy so in the proxy it is xpub
                       "stt_req_rep_port": 5556,  # REQ-REP control port for the stt pub sub
                       "tts_req_rep_port": 5557,  # REQ-REP port for the text to speech
                       }

    # ------------------------------------------------------------------------------------------------------------------
    # Start the pub sub proxy. Do this first to make sure it's there.
    mp.set_start_method("spawn")  # set this to make sure code works cross platform

    proxy_process = mp.Process(target=start_pubsub_proxy, kwargs={"port_config": port_config})
    proxy_process.start()
    sleep(t_sleep)
    print("proxy created")

    # ------------------------------------------------------------------------------------------------------------------
    # make the context for the main process and connect to the pubsub proxy
    context = zmq.Context()
    sockets_list = []

    socket_system_sync = context.socket(zmq.REP)
    socket_system_sync.bind("tcp://*:{}".format(port_config["system_sync_port"]))
    sockets_list.append(socket_system_sync)

    # make publish to proxy socket
    socket_publisher = context.socket(zmq.PUB)
    socket_publisher.connect("tcp://localhost:{}".format(port_config["pub_to_proxy_port"]))
    sockets_list.append(socket_publisher)

    # make subscribe to proxy socket
    socket_subscriber = context.socket(zmq.SUB)
    socket_subscriber.connect("tcp://localhost:{}".format(port_config["sub_to_proxy_port"]))
    socket_subscriber.setsockopt(zmq.SUBSCRIBE, b"CONTROL")
    sockets_list.append(socket_subscriber)

    # make poller because we are listening to both the subscriber and the stt_reply sockets
    poller = zmq.Poller()
    poller.register(socket_subscriber, zmq.POLLIN)

    sleep(t_sleep)

    # ------------------------------------------------------------------------------------------------------------------
    # start up the processes
    process_funcs = [control_main,
                     text_to_speech_main,
                     speech_to_text_main]

    process_list = start_all_processes(process_funcs, port_config)

    # wait to be told that all processes have connected their sockets and are ready to go.
    connected_modules = 0
    while connected_modules < len(process_funcs):
        # wait for sync request
        msg = socket_system_sync.recv()
        socket_system_sync.send(b"")
        connected_modules += 1
        print("The {} process has connected all sockets and has initialized all functionality.".format(msg.decode()))

    # append the proxy to the list of processes so we can shut the proxy process down later
    process_list.append(proxy_process)
    sleep(0.1)

    # ------------------------------------------------------------------------------------------------------------------
    # Publish start message
    socket_publisher.send_multipart([b"SYSTEM", b"START"])

    # Now just hold until we
    try:
        while True:
            socks = dict(poller.poll(100))  # poll for .1 ms don't block
            if socket_subscriber in socks and socks[socket_subscriber] == zmq.POLLIN:
                topic, message = socket_subscriber.recv_multipart()
                if topic == b"CONTROL" and message == b"SHUTDOWN":
                    break
            sleep(t_sleep)
    except KeyboardInterrupt:
        print("Interrupt received, stopping ...")
        # TODO figure out if it can be shut down cleanly with keyboard interrupt or if I need to do something different
    finally:
        print("Cleaning up ...")
        stop_all_processes(process_list)
        print("All processes stopped.")

        # Close sockets and context
        for sock in sockets_list:
            sock.setsockopt(zmq.LINGER, 0)
            sock.close()
        context.term()
        print("Main process shutdown.")


if __name__ == "__main__":
    run_main()
