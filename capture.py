import argparse
from NatNetClient import NatNetClient
from time import sleep, time
import logging
import msgpack as serializer
import zmq
from zmq.utils.monitor import recv_monitor_message
import json
import sys

assert zmq.__version__ > '15.1'

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
    parser = argparse.ArgumentParser(
        prog='capture',
         description='''
             This program captures data streamed from
             pupil labs and OptiTrack. The data is then
             saved as a json file which can be changed
             by passing a path to the output argument.''',
         epilog='''
             ''')
    
    parser.add_argument("--output",
                        default="output.json",
                        help="path to output file. (default: output.json)")
    parser.add_argument("--optitrack-ip",
                        default="127.0.0.1",
                        help="ip address for OptiTrack. (default: 127.0.0.1)")
    parser.add_argument("--optitrack-command-port",
                        default=1510,
                        type=int,
                        help="command port for OptiTrack. (default: 1510)")
    parser.add_argument("--optitrack-data-port",
                        default=1511,
                        type=int,
                        help="data port for OptiTrack. (default: 1511)")
    parser.add_argument("--optitrack-multicast-address",
                        default="239.255.42.99",
                        help="multicast address for OptiTrack. (default: 239.255.42.99)")
    parser.add_argument("--pupil-labs-ip",
                        default="127.0.0.1",
                        help="ip address for Pupil Labs. (default: 127.0.0.1)")
    parser.add_argument("--pupil-labs-port",
                        default=50020,
                        type=int,
                        help="port for Pupil Labs. (default: 50020)")
    parser.add_argument('--pupil-labs-off',
                        action='store_true',
                        help="don't record any data from pupil labs.")
    parser.add_argument('--pupil0-off',
                        action='store_true',
                        help="don't record any pupil.0 data from pupil labs.")
    parser.add_argument('--pupil1-off',
                        action='store_true',
                        help="don't record any pupil.1 data from pupil labs.")
    parser.add_argument('--optitrack-off',
                        action='store_true',
                        help="don't record any data from OptiTrack.")
    args = parser.parse_args()

    output_header = {}

    print( 'Starting program' )
    print( 'Pupil Labs:', not args.pupil_labs_off )

    if not args.pupil_labs_off:
        print( 'Pupil.0:', not args.pupil0_off )
        print( 'Pupil.1:', not args.pupil1_off )
        print( 'tcp://%s:%d' % (args.pupil_labs_ip, args.pupil_labs_port) )
    
        # tap into the IPC backbone of pupil capture
        ctx = zmq.Context()

        # the requester talks to Pupil remote and
        # recevied the session unique IPC SUB URL
        requester = ctx.socket(zmq.REQ)
        requester.connect( 'tcp://%s:%d' % (args.pupil_labs_ip, args.pupil_labs_port) )

        requester.send_string('SUB_PORT')
        ipc_sub_port = requester.recv().decode("utf-8")

        print( 'ipc_sub_port:', ipc_sub_port )

        print( 'tcp://%s:%s' % (args.pupil_labs_ip, ipc_sub_port) )

        # Subscribe to pupils
        if not args.pupil0_off:
            pupil0 = Msg_Receiver(
                ctx, 'tcp://%s:%s' % (args.pupil_labs_ip, ipc_sub_port),
                topics=('pupil.0',))
            
        if not args.pupil1_off:
            pupil1 = Msg_Receiver(
                ctx, 'tcp://%s:%s' % (args.pupil_labs_ip, ipc_sub_port),
                topics=('pupil.1',))
        sleep(1)

    print( 'OptiTrack:', not args.optitrack_off )

    if not args.optitrack_off:
        print( 'ip:', args.optitrack_ip )
        print( 'command port:', args.optitrack_command_port )
        print( 'data port:', args.optitrack_data_port )
        print( 'multicast address:', args.optitrack_multicast_address )
        
        # This will create a new NatNet client
        streamingClient = NatNetClient(args.optitrack_ip,
                                       args.optitrack_multicast_address,
                                       args.optitrack_command_port,
                                       args.optitrack_data_port)

        # Start up the streaming client now that the callbacks are set up.
        # This will run perpetually, and operate on a separate thread.
        streamingClient.run()

        print( streamingClient.get_version() )
        
        sleep(2)

        output_header['rigidBodyInfo'] = streamingClient.getRigidBodyDescription()

    
    input( 'Press Enter to continue and start recording...' )
    print( "Recording Started" )
    print( 'Press Ctrl-C to stop recording' )
    start_time = time()
    
    with open(args.output, 'w') as f:
        f.write('{\"static\": \n')
        f.write(json.dumps(output_header))
        f.write(',\n\"frames\": [\n')
        try:
            first_frame = True
            frame = 1
            st = time()
            while True:
                sft = time()
                if frame % 100 == 0:
                    et = time()
                    sys.stdout.write("\rframe: %d at %f fps" % (frame, 100.0/(et-st)))
                    sys.stdout.flush()
                    st = et
                
                obj = {}
                obj['frame'] = frame
                obj['time'] = time() - start_time
                
                if not args.optitrack_off:
                    streamingClient.lock()
                    
                if not args.pupil_labs_off:
                    if not args.pupil0_off:
                        pupil0_topic, pupil0_msg = pupil0.recv()
                        obj['pupil0'] = pupil0_msg
                    
                    if not args.pupil1_off:
                        pupil1_topic, pupil1_msg = pupil1.recv()
                        obj['pupil1'] = pupil1_msg
                    
                if not args.optitrack_off:
                    obj['rigidBodies'] = streamingClient.getRigidBodyList()
                
                if not args.optitrack_off:        
                    streamingClient.unlock()

                if not first_frame:
                    f.write(",\n")
                else:
                    first_frame = False
                
                f.write(json.dumps(obj))
                frame = frame + 1

                sleep(max(0, (1.0/70.0) - (time() - sft)))
                
        except KeyboardInterrupt:
            f.write(']}\n')
            f.close()
            print( "Done" )

