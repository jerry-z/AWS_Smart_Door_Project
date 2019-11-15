import json
import boto3
import time
import logging
import random
import base64
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
import sys
sys.path.insert(1, '/opt')
import cv2

logger = logging.getLogger()
logger.setLevel(logging.INFO)


dynamodb = boto3.resource('dynamodb')
table_p = dynamodb.Table('gate-passcodes')
table_v = dynamodb.Table('gate-visitors')

s3 = boto3.resource('s3')
s3_client = boto3.client('s3')
bucket = "gate-unknown-faces"
sns = boto3.client("sns", region_name="us-east-1")

owner_phone = "3322016289"
web_url = "http://i_am_davit.com.cn"

def lambda_handler(event, context):
    logger.info("lambda1 start")
    
    data = decode_data(event)
    
    have_face,faceId = get_face(data)
    
    logger.info("have face :{}".format(have_face))
    logger.info("faceId:{}".format(faceId))
    
    valid, name, phone = exist_visitor(have_face,faceId)
    print(valid)
    if have_face:
        if valid:
            logger.info("exist visitor ,name:{}".format(name))
            passcode = generate_passcode()
            store_passcode_record(passcode,faceId)
            logger.info("new passcode saved:{}".format(passcode))
            
            txt = msg_for_visitor(passcode)
        else:
            logger.info("new visitor")
            phone = owner_phone
            img_url = get_unknown_visitor_img()
            web_url = get_webpage(img_url)
            logger.info("web url is :{}".format(web_url))
            txt = msg_for_owner(web_url)
    
        send_message(phone,txt)
        logger.info("message sent to phone: {}".format(phone))



def decode_data(event):
    code = event['Records'][0]['kinesis']['data']
    code_b = code.encode("UTF-8")
    data_b = base64.b64decode(code_b)
    data = data_b.decode("UTF-8")
    logger.info(data)
    data = json.loads(data)
    return data
    
def get_face(data):
    face_data = data["FaceSearchResponse"]
    if len(face_data) ==0:
        return False, None
    match_faces = face_data[0]["MatchedFaces"]
    if len(match_faces) == 0:
        return True,None
    face = match_faces[0]
    faceId = face["Face"]["FaceId"]
    return True,faceId

def exist_visitor(valid,faceId):
    if not valid:
        return False,None,None
    if faceId is None:
        return False,None,None
    responce = table_v.get_item(Key={"faceId": faceId})
    if "Item" not in responce:
        return False,None,None
    visitor = responce["Item"]
    return True,visitor["name"],visitor["phoneNumber"]

def generate_passcode():
    PIN = ""
    for i in range(6):
        PIN = PIN + str(random.randint(0,9))
    passcode = PIN
    return passcode

def store_passcode_record(passcode,faceId):
    expiration_time = int(time.time() + 300)
    print(type(expiration_time))
    table_p.put_item(
        Item={
            "passcode":passcode,
            "faceId": faceId,
            "expirationTime": expiration_time
        }
    )

def msg_for_visitor(passcode):
    txt = "hi, your passcode is:" + str(passcode) + "\nPlease use this url to get into the door\n"+"http://gate-visitors.s3-website-us-east-1.amazonaws.com"
    return txt
def msg_for_owner(web_url):
    txt = "hi,master. There is a stranger trying to get into your palace, please set the permission.\n" + web_url 
    return txt

def send_message(phone,txt):
    
    sns.publish(
        PhoneNumber= "1" + str(phone),
        Message=txt
    )

#         ##############################################################
def get_unknown_visitor_img():

    logger.info("we are in the function")
    hls_stream_ARN = "arn:aws:kinesisvideo:us-east-1:899580659559:stream/gate-RecognizeVisitor/1571965987636"
    STREAM_NAME = "gate-RecognizeVisitor"
    kvs = boto3.client("kinesisvideo")
    
    response = kvs.get_data_endpoint(
        StreamARN=hls_stream_ARN,
        APIName='GET_MEDIA'
    )
    
    endpoint_url_string = response['DataEndpoint']
    
    streaming_client = boto3.client(
        'kinesis-video-media', 
        endpoint_url=endpoint_url_string, 
        #region_name='us-east-1'
    )
    
    kinesis_stream = streaming_client.get_media(
        StreamARN=hls_stream_ARN,
        StartSelector={'StartSelectorType': 'NOW'}
    )
    
    with open('/tmp/stream.mkv', 'wb') as f:
        streamBody = kinesis_stream['Payload'].read(1024*1024)
        logger.info('STREAM READ FINISHED')
        f.write(streamBody)
        logger.info("saved now reading")
        cap = cv2.VideoCapture('/tmp/stream.mkv')
        ret, frame = cap.read() 
        cv2.imwrite('/tmp/frame.jpg', frame)
        logger.info("img got")
        
        img_name = "unknown.jpg" 
        s3_client.upload_file(
            '/tmp/frame.jpg',
            bucket, 
            img_name,
            ExtraArgs={'ACL':'public-read'}
        )
        
        cap.release()
        logger.info("uploaded")
    
    # stream_payload = kinesis_stream['Payload']
    # logger.info("we get the stream")
    # stream_payload = stream_payload.read(1000000)
    # logger.info('STREAM READ FINISHED')
    # f = open("/tmp/fragments.mkv", 'w+b')
    # f.write(stream_payload)
    # f.close() 
    # logger.info("saved now reading")
    # cap= cv2.VideoCapture('/tmp/fragments.mkv')
    # ret, frame = cap.read()
    # cv2.imwrite('/tmp/img.jpg',frame)
    # logger.info("img got")
    
    # count = sum(1 for _ in s3.Bucket(bucket).objects.all())
    # img_name = "unknown"+ str(count + 1) + ".jpg"
    
    
    # with open("/tmp/img.jpg", "rb") as f:
    #     s3.upload_fileobj(f,bucket,img_name)
    # logger.info("uploaded")
    img_url = "https://" + bucket + ".s3.amazonaws.com/" + img_name
    return img_url


def get_webpage(img_url):
    
    ####################################################################3
    web_url = "http://gate-owner.s3-website-us-east-1.amazonaws.com"
    return web_url
