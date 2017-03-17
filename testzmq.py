'''
(*)~---------------------------------------------------------------------------
Pupil - eye tracking platform
Copyright (C) 2012-2017  Pupil Labs
Distributed under the terms of the GNU
Lesser General Public License (LGPL v3.0).
See COPYING and COPYING.LESSER for license details.
---------------------------------------------------------------------------~(*)
'''


'''
This file contains convenience classes for communication with
the Pupil IPC Backbone.
'''

import logging
import msgpack as serializer
import zmq
from zmq.utils.monitor import recv_monitor_message
# import ujson as serializer # uncomment for json serialization

assert zmq.__version__ > '15.1'


class ZMQ_handler(logging.Handler):
    '''
    A handler that sends log records as serialized strings via zmq
    '''
    def __init__(self, ctx, ipc_pub_url):
        super().__init__()
        self.socket = Msg_Dispatcher(ctx, ipc_pub_url)

    def emit(self, record):
        self.socket.send_string('logging.{0}'.format(record.levelname.lower()),
                         record.__dict__)


class Msg_Receiver(object):
    '''
    Recv messages on a sub port.
    Not threadsafe. Make a new one for each thread
    __init__ will block until connection is established.
    '''
    def __init__(self, ctx, url, topics=(), block_until_connected=True):
        self.socket = zmq.Socket(ctx, zmq.SUB)
        assert type(topics) != str

        if block_until_connected:
            # connect node and block until a connecetion has been made
            monitor = self.socket.get_monitor_socket()
            self.socket.connect(url)
            while True:
                status = recv_monitor_message(monitor)
                if status['event'] == zmq.EVENT_CONNECTED:
                    break
                elif status['event'] == zmq.EVENT_CONNECT_DELAYED:
                    pass
                else:
                    raise Exception("ZMQ connection failed")
            self.socket.disable_monitor()
        else:
            self.socket.connect(url)

        for t in topics:
            self.subscribe(t)

    def subscribe(self, topic):
        self.socket.setsockopt_string(zmq.SUBSCRIBE, topic)

    def unsubscribe(self, topic):
        self.socket.unsubscribe(topic)

    def recv(self):
        '''Recv a message with topic, payload.
        Topic is a utf-8 encoded string. Returned as unicode object.
        Payload is a msgpack serialized dict. Returned as a python dict.
        Any addional message frames will be added as a list
        in the payload dict with key: '__raw_data__' .
        '''
        topic = self.socket.recv_string()
        payload = serializer.loads(self.socket.recv(), encoding='utf-8')
        extra_frames = []
        while self.socket.get(zmq.RCVMORE):
            extra_frames.append(self.socket.recv())
        if extra_frames:
            payload['__raw_data__'] = extra_frames
        return topic, payload

    @property
    def new_data(self):
        return self.socket.get(zmq.EVENTS)

    def __del__(self):
        self.socket.close()

if __name__ == '__main__':
    from time import sleep, time
    # tap into the IPC backbone of pupil capture
    ctx = zmq.Context()

    # the requester talks to Pupil remote and
    # recevied the session unique IPC SUB URL
    requester = ctx.socket(zmq.REQ)
    requester.connect('tcp://127.0.0.1:50020')

    requester.send_string('SUB_PORT')
    ipc_sub_port = requester.recv().decode("utf-8")

    print('ipc_sub_port:', ipc_sub_port)
    print('ipc_pub_port:', ipc_pub_port)

    print('tcp://127.0.0.1:{}'.format(ipc_sub_port))

    # more topics: gaze, pupil, logging, ...
    pupil0 = Msg_Receiver(
        ctx, 'tcp://127.0.0.1:{}'.format(ipc_sub_port),
        topics=('pupil.0',))
    pupil1 = Msg_Receiver(
        ctx, 'tcp://127.0.0.1:{}'.format(ipc_sub_port),
        topics=('pupil.1',))
    sleep(1)

    while True:
        print("Frame Start")
        topic, msg = pupil0.recv()
        print('%s: %s\n\n' % (topic, msg))
        topic, msg = pupil1.recv()
        print('%s: %s\n\n' % (topic, msg))
        print("Frame END!!!")
