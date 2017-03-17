### Pupil Labs and OptiTrack Data Recorder ###

A simple python script that can record data from Pupil Labs and OptiTrack. The data is saved to a json file.

For the python script to work you will need to setup Motive to broadcast it's data over the network. As well as have pupil labs running and streaming its data. Note that some of the options allow you to ignore some of the data. For example the following command will not record OptiTrack data and there for you won't need to have Motive running:

python capture.py --optitrack-off

For a list of options type the following in the command prompt on Windows:

python capture.py -h

The output json will look similiar to the following:

```json
{"static": {
	"rigidBodyInfo": [{
		"id": 1, 
		"timestamp": [0.0, 0.0, 0.0], 
		"parentID": 4294967295, 
		"name": "RigidBody 1"
	}, {
		"id": 2, 
		"timestamp": [0.0, 0.0, 0.0], 
		"parentID": 4294967295, 
		"name": "RigidBody 2"
	}]},
"frames": [{
	"frame": 1,
	"time": 0.015996456146240234,
	"pupil0": {
		"id": 0, 
		"topic": "pupil",
		"timestamp": 73495.727, 
		"diameter": 0.0,
		"method": "2d c++", 
		"ellipse": {
			"center": [0.0, 0.0], 
			"angle": -90.0, 
			"axes": [0.0, 0.0]
		}, 
		"norm_pos": [0.0, 1.0], 
		"confidence": 0.0},
	"pupil1": {
		"id": 1, 
		"topic": "pupil", 
		"timestamp": 73495.728, 
		"diameter": 0.0,
		"method": "2d c++", 
		"ellipse": {
			"center": [0.0, 0.0], 
			"angle": -90.0, 
			"axes": [0.0, 0.0]
		},
		"norm_pos": [0.0, 1.0], 
		"confidence": 0.0},
	"rigidBodies": [{
		"id": 1,
		"valid": false, 
		"position": [-0.0, 0.0, 0.0],
		"rotation": [-0.0, 0.0, 0.0, -1.0],	
		"markerCount": 3, 
		"markers": [{
			"id": 1, 
			"size": [0.0], 
			"position": [-0.0, 0.0, 0.0]
		}, {
			"id": 2, 
			"size": [0.0], 
			"position": [-0.0, 0.0, 0.0]
		}, {
			"id": 3, 
			"size": [0.0], 
			"position": [-0.0, 0.0, 0.0]
		}]
	}, 
	...
```

Note that depending on what options are selected when you run the command some of the json elements might not appear.