'''
This file was taken from the NatNet SDK and modified slightly.
NatNet Version 2.10.0 (06/15/2016)
'''

import socket
import struct
from threading import Thread, Lock

def trace( *args ):
    pass # print( "".join(map(str,args)) )

# Create structs for reading various object types to speed up parsing.
Vector3 = struct.Struct( '<fff' )
Quaternion = struct.Struct( '<ffff' )
FloatValue = struct.Struct( '<f' )
DoubleValue = struct.Struct( '<d' )

class NatNetClient:
    def __init__( self, ip_address="127.0.0.1", multicast_address="239.255.42.99", cmd_port=1510, data_port=1511):
        # Change this value to the IP address of the NatNet server.
        self.serverIPAddress = ip_address

        # This should match the multicast address listed in Motive's streaming settings.
        self.multicastAddress = multicast_address

        # NatNet Command channel
        self.commandPort = cmd_port
        
        # NatNet Data channel     
        self.dataPort = data_port

        # Set this to a callback method of your choice to receive new frame.
        self.newFrameListener = None

        # Set this to a callback method of your choice to receive per-rigid-body data at each frame.
        self.rigidBodyDictListener = None

        # Set this to a callback method of your choice to receive per-rigid-body data descriptions.
        self.rigidBodyDictDescriptionListener = None
        
        # NatNet stream version. This will be updated to the actual version the server is using during initialization.
        self.__natNetStreamVersion = (3,0,0,0)

        # List of rigid bodies
        self.rigidBodyDescription = []
        self.rigidBodyList = []

        # Lock for Client
        self._lock = Lock()

    # Client/server message ids
    NAT_PING                  = 0 
    NAT_PINGRESPONSE          = 1
    NAT_REQUEST               = 2
    NAT_RESPONSE              = 3
    NAT_REQUEST_MODELDEF      = 4
    NAT_MODELDEF              = 5
    NAT_REQUEST_FRAMEOFDATA   = 6
    NAT_FRAMEOFDATA           = 7
    NAT_MESSAGESTRING         = 8
    NAT_DISCONNECT            = 9 
    NAT_UNRECOGNIZED_REQUEST  = 100

    # Create a data socket to attach to the NatNet stream
    def __createDataSocket( self, port ):
        result = socket.socket( socket.AF_INET,     # Internet
                              socket.SOCK_DGRAM,
                              socket.IPPROTO_UDP)    # UDP
        result.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        result.bind( ('', port) )

        mreq = struct.pack("4sl", socket.inet_aton(self.multicastAddress), socket.INADDR_ANY)
        result.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        return result

    # Create a command socket to attach to the NatNet stream
    def __createCommandSocket( self ):
        result = socket.socket( socket.AF_INET, socket.SOCK_DGRAM )
        result.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        result.bind( ('', 0) )
        result.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        return result

    # Unpack a rigid body object from a data packet
    def __unpackRigidBody( self, data ):
        rigidBody = {}
        
        offset = 0

        # ID (4 bytes)
        id = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        trace( "ID:", id )

        for rb in self.rigidBodyList:
            if rb['id'] == id:
                rigidBody = rb
                break
                
        # Position and orientation
        pos = Vector3.unpack( data[offset:offset+12] )
        offset += 12
        trace( "\tPosition:", pos[0],",", pos[1],",", pos[2] )
        rot = Quaternion.unpack( data[offset:offset+16] )
        offset += 16
        trace( "\tOrientation:", rot[0],",", rot[1],",", rot[2],",", rot[3] )

        if rigidBody is not None:
            rigidBody['position'] = pos
            rigidBody['rotation'] = rot

        # Marker count (4 bytes)
        markerCount = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        markerCountRange = range( 0, markerCount )
        trace( "\tMarker Count:", markerCount )

        if rigidBody is not None:
            rigidBody['markerCount'] = markerCount
            rigidBody['markers'] = []

        if rigidBody is not None:
            for i in markerCountRange:
                rigidBody['markers'].append( {} )

        # Send information to any listener.
        if self.rigidBodyDictListener is not None:
            self.rigidBodyDictListener( id, pos, rot )

        # Marker positions
        for i in markerCountRange:
            pos = Vector3.unpack( data[offset:offset+12] )
            offset += 12
            trace( "\tMarker", i, ":", pos[0],",", pos[1],",", pos[2] )

            if rigidBody is not None:
                rigidBody['markers'][i]['position'] = pos
            

        if( self.__natNetStreamVersion[0] >= 2 ):
            # Marker ID's
            for i in markerCountRange:
                id = int.from_bytes( data[offset:offset+4], byteorder='little' )
                offset += 4
                trace( "\tMarker ID", i, ":", id )

                if rigidBody is not None:
                    rigidBody['markers'][i]['id'] = id

            # Marker sizes
            for i in markerCountRange:
                size = FloatValue.unpack( data[offset:offset+4] )
                offset += 4
                trace( "\tMarker Size", i, ":", size[0] )

                if rigidBody is not None:
                    rigidBody['markers'][i]['size'] = size
                
            markerError, = FloatValue.unpack( data[offset:offset+4] )
            offset += 4
            trace( "\tMarker Error:", markerError )

        # Version 2.6 and later
        if( ( ( self.__natNetStreamVersion[0] == 2 ) and ( self.__natNetStreamVersion[1] >= 6 ) ) or self.__natNetStreamVersion[0] > 2 or self.__natNetStreamVersion[0] == 0 ):
            param, = struct.unpack( 'h', data[offset:offset+2] )
            trackingValid = ( param & 0x01 ) != 0
            offset += 2
            trace( "\tTracking Valid:", 'True' if trackingValid else 'False' )

            if rigidBody is not None:
               rigidBody['valid'] = trackingValid
        
        return offset

    # Unpack a skeleton object from a data packet
    def __unpackSkeleton( self, data ):
        offset = 0
        
        id = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        trace( "ID:", id )
        
        rigidBodyCount = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        trace( "Rigid Body Count:", rigidBodyCount )
        for j in range( 0, rigidBodyCount ):
            offset += self.__unpackRigidBody( data[offset:] )

        return offset

    # Unpack data from a motion capture frame message
    def __unpackMocapData( self, data ):
        trace( "Begin MoCap Frame\n-----------------\n" )

        data = memoryview( data )
        offset = 0
        
        # Frame number (4 bytes)
        frameNumber = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        trace( "Frame #:", frameNumber )

        # Marker set count (4 bytes)
        markerSetCount = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        trace( "Marker Set Count:", markerSetCount )

        for i in range( 0, markerSetCount ):
            # Model name
            modelName, separator, remainder = bytes(data[offset:]).partition( b'\0' )
            offset += len( modelName ) + 1
            trace( "Model Name:", modelName.decode( 'utf-8' ) )

            # Marker count (4 bytes)
            markerCount = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            trace( "Marker Count:", markerCount )

            for j in range( 0, markerCount ):
                pos = Vector3.unpack( data[offset:offset+12] )
                offset += 12
                #trace( "\tMarker", j, ":", pos[0],",", pos[1],",", pos[2] )
                 
        # Unlabeled markers count (4 bytes)
        unlabeledMarkersCount = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        trace( "Unlabeled Markers Count:", unlabeledMarkersCount )

        for i in range( 0, unlabeledMarkersCount ):
            pos = Vector3.unpack( data[offset:offset+12] )
            offset += 12
            trace( "\tMarker", i, ":", pos[0],",", pos[1],",", pos[2] )

        # Rigid body count (4 bytes)
        rigidBodyCount = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        trace( "Rigid Body Count:", rigidBodyCount )

        for i in range( 0, rigidBodyCount ):
            offset += self.__unpackRigidBody( data[offset:] )

        # Version 2.1 and later
        skeletonCount = 0
        if( ( self.__natNetStreamVersion[0] == 2 and self.__natNetStreamVersion[1] > 0 ) or self.__natNetStreamVersion[0] > 2 ):
            skeletonCount = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            trace( "Skeleton Count:", skeletonCount )
            for i in range( 0, skeletonCount ):
                offset += self.__unpackSkeleton( data[offset:] )

        # Labeled markers (Version 2.3 and later)
        labeledMarkerCount = 0
        if( ( self.__natNetStreamVersion[0] == 2 and self.__natNetStreamVersion[1] > 3 ) or self.__natNetStreamVersion[0] > 2 ):
            labeledMarkerCount = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            trace( "Labeled Marker Count:", labeledMarkerCount )
            for i in range( 0, labeledMarkerCount ):
                id = int.from_bytes( data[offset:offset+4], byteorder='little' )
                offset += 4
                pos = Vector3.unpack( data[offset:offset+12] )
                offset += 12
                size = FloatValue.unpack( data[offset:offset+4] )
                offset += 4

                # Version 2.6 and later
                if( ( self.__natNetStreamVersion[0] == 2 and self.__natNetStreamVersion[1] >= 6 ) or self.__natNetStreamVersion[0] > 2 or major == 0 ):
                    param, = struct.unpack( 'h', data[offset:offset+2] )
                    offset += 2
                    occluded = ( param & 0x01 ) != 0
                    pointCloudSolved = ( param & 0x02 ) != 0
                    modelSolved = ( param & 0x04 ) != 0

        # Force Plate data (version 2.9 and later)
        if( ( self.__natNetStreamVersion[0] == 2 and self.__natNetStreamVersion[1] >= 9 ) or self.__natNetStreamVersion[0] > 2 ):
            forcePlateCount = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            trace( "Force Plate Count:", forcePlateCount )
            for i in range( 0, forcePlateCount ):
                # ID
                forcePlateID = int.from_bytes( data[offset:offset+4], byteorder='little' )
                offset += 4
                trace( "Force Plate", i, ":", forcePlateID )

                # Channel Count
                forcePlateChannelCount = int.from_bytes( data[offset:offset+4], byteorder='little' )
                offset += 4

                # Channel Data
                for j in range( 0, forcePlateChannelCount ):
                    trace( "\tChannel", j, ":", forcePlateID )
                    forcePlateChannelFrameCount = int.from_bytes( data[offset:offset+4], byteorder='little' )
                    offset += 4
                    for k in range( 0, forcePlateChannelFrameCount ):
                        forcePlateChannelVal = int.from_bytes( data[offset:offset+4], byteorder='little' )
                        offset += 4
                        trace( "\t\t", forcePlateChannelVal )

        # Latency
        latency, = FloatValue.unpack( data[offset:offset+4] )
        offset += 4
        
        # Timecode            
        timecode = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4
        timecodeSub = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4

        # Timestamp (increased to double precision in 2.7 and later)
        if( ( self.__natNetStreamVersion[0] == 2 and self.__natNetStreamVersion[1] >= 7 ) or self.__natNetStreamVersion[0] > 2 ):
            timestamp, = DoubleValue.unpack( data[offset:offset+8] )
            offset += 8
        else:
            timestamp, = FloatValue.unpack( data[offset:offset+4] )
            offset += 4

        # Frame parameters
        param, = struct.unpack( 'h', data[offset:offset+2] )
        isRecording = ( param & 0x01 ) != 0
        trackedModelsChanged = ( param & 0x02 ) != 0
        offset += 2

        # Send information to any listener.
        if self.newFrameListener is not None:
            self.newFrameListener( frameNumber, markerSetCount, unlabeledMarkersCount, rigidBodyCount, skeletonCount,
                                  labeledMarkerCount, latency, timecode, timecodeSub, timestamp, isRecording, trackedModelsChanged )

    # Unpack a marker set description packet
    def __unpackMarkerSetDescription( self, data ):
        offset = 0

        name, separator, remainder = bytes(data[offset:]).partition( b'\0' )
        offset += len( name ) + 1
        trace( "Markerset Name:", name.decode( 'utf-8' ) )
        
        markerCount = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4

        for i in range( 0, markerCount ):
            name, separator, remainder = bytes(data[offset:]).partition( b'\0' )
            offset += len( name ) + 1
            trace( "\tMarker Name:", name.decode( 'utf-8' ) )
        
        return offset

    # Unpack a rigid body description packet
    def __unpackRigidBodyDescription( self, data ):
        offset = 0
        name = None

        # Version 2.0 or higher
        if( self.__natNetStreamVersion[0] >= 2 ):
            name, separator, remainder = bytes(data[offset:]).partition( b'\0' )
            offset += len( name ) + 1
            trace( "\tMarker Name:", name.decode( 'utf-8' ) )

        id = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4

        parentID = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4

        timestamp = Vector3.unpack( data[offset:offset+12] )
        offset += 12

        if self.rigidBodyDictDescriptionListener is not None:
            self.rigidBodyDictDescriptionListener( id, name.decode( 'utf-8' ), parentID, timestamp )

        rb_info = {}
        rb_info['id'] = id
        rb_info['name'] = name.decode( 'utf-8' )
        rb_info['parentID'] = parentID
        rb_info['timestamp'] = timestamp

        rb = {}
        rb['id'] = id

        self.rigidBodyDescription.append( rb_info )
        self.rigidBodyList.append( rb )
        
        return offset

    # Unpack a skeleton description packet
    def __unpackSkeletonDescription( self, data ):
        offset = 0

        name, separator, remainder = bytes(data[offset:]).partition( b'\0' )
        offset += len( name ) + 1
        trace( "\tMarker Name:", name.decode( 'utf-8' ) )
        
        id = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4

        rigidBodyCount = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4

        for i in range( 0, rigidBodyCount ):
            offset += self.__unpackRigidBodyDescription( data[offset:] )

        return offset

    # Unpack a data description packet
    def __unpackDataDescriptions( self, data ):
        # Reset Rigid Body List
        self.rigidBodyDescription = []
        self.rigidBodyList = []
        
        offset = 0
        datasetCount = int.from_bytes( data[offset:offset+4], byteorder='little' )
        offset += 4

        for i in range( 0, datasetCount ):
            type = int.from_bytes( data[offset:offset+4], byteorder='little' )
            offset += 4
            if( type == 0 ):
                offset += self.__unpackMarkerSetDescription( data[offset:] )
            elif( type == 1 ):
                offset += self.__unpackRigidBodyDescription( data[offset:] )
            elif( type == 2 ):
                offset += self.__unpackSkeletonDescription( data[offset:] )
            
    def __dataThreadFunction( self, socket ):
        while True:
            # Block for input
            data, addr = socket.recvfrom( 32768 ) # 32k byte buffer size
            if( len( data ) > 0 ):
                self.lock()
                self.__processMessage( data )
                self.unlock()

    def __processMessage( self, data ):
        trace( "Begin Packet\n------------\n" )

        messageID = int.from_bytes( data[0:2], byteorder='little' )
        trace( "Message ID:", messageID )
        
        packetSize = int.from_bytes( data[2:4], byteorder='little' )
        trace( "Packet Size:", packetSize )

        offset = 4
        if( messageID == self.NAT_FRAMEOFDATA ):
            self.__unpackMocapData( data[offset:] )
        elif( messageID == self.NAT_MODELDEF ):
            self.__unpackDataDescriptions( data[offset:] )
        elif( messageID == self.NAT_PINGRESPONSE ):
            offset += 256   # Skip the sending app's Name field
            offset += 4     # Skip the sending app's Version info
            self.__natNetStreamVersion = struct.unpack( 'BBBB', data[offset:offset+4] )
            offset += 4
        elif( messageID == self.NAT_RESPONSE ):
            if( packetSize == 4 ):
                commandResponse = int.from_bytes( data[offset:offset+4], byteorder='little' )
                offset += 4
            else:
                message, separator, remainder = bytes(data[offset:]).partition( b'\0' )
                offset += len( message ) + 1
                trace( "Command response:", message.decode( 'utf-8' ) )
        elif( messageID == self.NAT_UNRECOGNIZED_REQUEST ):
            trace( "Received 'Unrecognized request' from server" )
        elif( messageID == self.NAT_MESSAGESTRING ):
            message, separator, remainder = bytes(data[offset:]).partition( b'\0' )
            offset += len( message ) + 1
            trace( "Received message from server:", message.decode( 'utf-8' ) )
        else:
            trace( "ERROR: Unrecognized packet type" )
            
        trace( "End Packet\n----------\n" )

    def lock( self ):
        self._lock.acquire()

    def unlock( self ):
        self._lock.release()

    def get_version( self ):
        return self.__natNetStreamVersion

    def getRigidBodyList( self ):
        return self.rigidBodyList

    def getRigidBodyDescription( self ):
        return self.rigidBodyDescription
            
    def sendCommand( self, command, commandStr, socket, address ):
        # Compose the message in our known message format
        if( command == self.NAT_REQUEST_MODELDEF or command == self.NAT_REQUEST_FRAMEOFDATA ):
            packetSize = 0
            commandStr = ""
        elif( command == self.NAT_REQUEST ):
            packetSize = len( commandStr ) + 1
        elif( command == self.NAT_PING ):
            commandStr = "Ping"
            packetSize = len( commandStr ) + 1

        data = command.to_bytes( 2, byteorder='little' )
        data += packetSize.to_bytes( 2, byteorder='little' )
        
        data += commandStr.encode( 'utf-8' )
        data += b'\0'

        socket.sendto( data, address )

    def run( self ):
        # Create the data socket
        self.dataSocket = self.__createDataSocket( self.dataPort )
        if( self.dataSocket is None ):
            print( "Could not open data channel" )
            exit

        # Create the command socket
        self.commandSocket = self.__createCommandSocket()
        if( self.commandSocket is None ):
            print( "Could not open command channel" )
            exit

        # Create a separate thread for receiving data packets
        dataThread = Thread( target = self.__dataThreadFunction, args = (self.dataSocket, ))
        dataThread.start()

        # Create a separate thread for receiving command packets
        commandThread = Thread( target = self.__dataThreadFunction, args = (self.commandSocket, ))
        commandThread.start()

        self.sendCommand( self.NAT_REQUEST_MODELDEF, "", self.commandSocket, (self.serverIPAddress, self.commandPort) )
    
