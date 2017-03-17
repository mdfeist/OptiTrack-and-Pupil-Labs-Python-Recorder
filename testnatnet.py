from NatNetClient import NatNetClient
from time import sleep

# This is a callback function that gets connected to the NatNet client and called once per mocap frame.
def receiveNewFrame( frameNumber, markerSetCount, unlabeledMarkersCount, rigidBodyCount, skeletonCount,
                    labeledMarkerCount, latency, timecode, timecodeSub, timestamp, isRecording, trackedModelsChanged ):
    print( "Received frame", frameNumber )

# This is a callback function that gets connected to the NatNet client. It is called once per rigid body per frame
def receiveRigidBodyFrame( id, position, rotation ):
    print( "Received frame for rigid body", id )

def receiveRigidBodyDescription( id, name, parentID, timestamp):
    print( "Received description for rigid body", id, "with name", name )

# This will create a new NatNet client
streamingClient = NatNetClient("192.168.184.32", "239.255.42.99")

# Configure the streaming client to call our rigid body handler on the emulator to send data out.
streamingClient.newFrameListener = receiveNewFrame
streamingClient.rigidBodyListener = receiveRigidBodyFrame
streamingClient.rigidBodyDescriptionListener = receiveRigidBodyDescription

# Start up the streaming client now that the callbacks are set up.
# This will run perpetually, and operate on a separate thread.
streamingClient.run()

print( streamingClient.get_version() )

while True:
    print( "running..." )
    streamingClient.lock()
    print( streamingClient.getRigidBodyList() )
    streamingClient.unlock()
    sleep(1)
