import boto3
import cv2
import time
import json

# make sure to use the right ARN here:
def this_is_function():
	hls_stream_ARN = "arn:aws:kinesisvideo:us-east-1:899580659559:stream/gate-RecognizeVisitor/1571965987636"

	STREAM_NAME = "gate-RecognizeVisitor"


	kvs = boto3.client("kinesisvideo")

	# Now try getting video chunks using GetMedia

	response = kvs.get_data_endpoint(
	    #StreamName=STREAM_NAME,
	    StreamARN=hls_stream_ARN,
	    APIName='GET_MEDIA'
	)

	print("Getting data endpoint...", response)

	endpoint_url_string = response['DataEndpoint']

	streaming_client = boto3.client(
		'kinesis-video-media', 
		endpoint_url=endpoint_url_string, 
		#region_name='us-east-1'
	)

	kinesis_stream = streaming_client.get_media(
		StreamARN=hls_stream_ARN,
		#StartSelector={'StartSelectorType': 'EARLIEST'}
		StartSelector={
	        'StartSelectorType': 'NOW'
	    	}

	)
	print("!!!!!!!!!!!1")
	stream_payload = kinesis_stream['Payload']
	stream_payload = stream_payload.read(1000000)
	return stream_payload


stream_payload = this_is_function()
print(type(stream_payload))
print("Received stream payload.")
ret, frame = cv2.VideoCapture(stream_payload).read()
# f = open("fragments.mkv", 'w+b')
# f.write(stream_payload)
# f.close() 
# print("Saved to a file and read.")
# cap= cv2.VideoCapture('fragments.mkv')
# ret, frame = cap.read()
cv2.imwrite('img.jpg',frame)
