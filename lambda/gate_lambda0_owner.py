import json
import boto3
import time
import logging
import random
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)


dynamodb = boto3.resource('dynamodb')
table_p = dynamodb.Table('gate-passcodes')
table_v = dynamodb.Table('gate-visitors')

s3 = boto3.resource('s3')
s3_client = boto3.client('s3')
bucket1='gate-known-faces'
bucket2 = 'gate-unknown-faces'
sns = boto3.client("sns", region_name="us-east-1")

rekognition=boto3.client('rekognition')
collection_id='gate-Collection'




def lambda_handler(event, context):
    logger.info("lambda0 for user start")
    
    name, phone, img = get_info_from_owner_request(event)
    if None in [name,phone,img]:
        return give_failure_response_body("sorry,we don't have enough imformation to update the new visitor")
    if phone_check(phone) is False:
        return give_failure_response_body("sorry. The phone number:{} is not a correct 10 digitnumber.Please input a valid phone number like 111-111-1111.".format(phone))

    img_name = save_known_img(img,name)
    faceId = add_faces_to_collection(img_name)
    if faceId is None:
        return give_failure_response_body("sorry,we don't have enough imformation to update the new visitor")
    
    logger.info("get all the needed information for the new visitor")
    
    logger.info("visitor image saved")
    store_visitor_record(faceId,name,phone,img_name)
    logger.info("visitor imformation saved")
    
    passcode = generate_passcode()
    logger.info("passcode generated:{}".format(passcode))
    store_passcode_record(passcode,faceId)
    logger.info("passcode information saved")
    send_message(phone,passcode)
    logger.info("message sent to the new visitor")
    
    delete_unknown_img(img)
    
    return give_success_response_body("new visitor updated, we have sent the passcode to the phone:{}".format(phone))








def phone_check(phone):
    phone = phone.replace('-', '')
    if len(phone) != 10:
        return False
    for i in phone:
        if not i.isalnum():
            return False
    return 


def get_info_from_owner_request(event):
    body = event
    if "messages" not in body:
        logger.error("body type error")
        return None,None,None
    messages = event["messages"]
    if not isinstance(messages,list) or len(messages) < 1:
        logger.error("messages type error or no message")
        return None,None,None
    message = messages[0]
    if "unconstructed" not in message:
        logger.error("message missing unconstructed")
        return None,None,None
    if "name" not in message["unconstructed"]: 
        logger.error("message missing name")
        return None,None,None
    if "phone" not in message["unconstructed"]: 
        logger.error("message missing phone")
        return None,None,None
    if "img" not in message["unconstructed"]: 
        logger.error("message missing img")
        return None,None,None
    name = message["unconstructed"]["name"]
    phone = message["unconstructed"]["phone"]
    img = message["unconstructed"]["img"]
    
    
    img = img.split('/')[-1]
    return name, phone, img




def save_known_img(img,name):
    img_str = name + ".jpg"
    logger.info("new visitor img is {}".format(img))
    s3_client.download_file(bucket2, img, '/tmp/visitor.jpg')
    try:
        response = s3_client.upload_file('/tmp/visitor.jpg', bucket1, img_str, ExtraArgs={'ACL':'public-read'})
    except ClientError as e:
        logging.error(e)
    logger.info("known added")
    return img_str

def delete_unknown_img(img):
    
    s3.Object(bucket2, img).delete()
    logger.info("unknown deleted")

    
    
def add_faces_to_collection(photo):
    
    response=rekognition.index_faces(CollectionId=collection_id,
                                Image={'S3Object':{'Bucket':bucket1,'Name':photo}},
                                ExternalImageId=photo,
                                MaxFaces=1,
                                QualityFilter="AUTO",
                                DetectionAttributes=['ALL'])

    # logger.debug('Results for ' + photo) 	
    # logger.debug('Faces indexed:')						
    for faceRecord in response['FaceRecords']:
         logger.info('  Face ID: ' + faceRecord['Face']['FaceId'] + '  Location: {}'.format(faceRecord['Face']['BoundingBox']))
    # logger.debug('Faces not indexed:')
    # for unindexedFace in response['UnindexedFaces']:
    #     logger.debug(' Location: {}'.format(unindexedFace['FaceDetail']['BoundingBox']))
    #     logger.debug(' Reasons:')
    #     for reason in unindexedFace['Reasons']:
    #         logger.debug('   ' + reason)
    faceId = response['FaceRecords'][0]['Face']['FaceId']
    return faceId
    
def store_visitor_record(faceId,name,phone,img_str):
    named_tuple = time.localtime() # get struct_time
    time_string = time.strftime("%m-%d-%YT%H:%M:%S", named_tuple)
    table_v.put_item(
        Item={
            "faceId": faceId,
            "name": name,
            "phoneNumber": phone,
            "photos": [
                {
                 "bucket": bucket1,
                 "createdTimeStamp": time_string,
                "objectKey": img_str
                }
            ]
        }
    )

def generate_passcode():
    PIN = ""
    for i in range(6):
        PIN = PIN + str(random.randint(0,9))
    passcode = PIN
    return passcode


def store_passcode_record(passcode,faceId):
    expiration_time = int(time.time() + 300)
    # print(type(expiration_time))
    table_p.put_item(
        Item={
            "passcode":passcode,
            "faceId": faceId,
            "expirationTime": expiration_time
        }
    )


def send_message(phone,passcode):
    txt = "hi, your passcode is:" + str(passcode) + "\nPlease use this url to get into the door\n"+"http://gate-visitors.s3-website-us-east-1.amazonaws.com"
    sns.publish(
        PhoneNumber= "1" + str(phone),
        Message=txt
    )


def give_success_response_body(visitor):
    text = ""
    body = {
        "messages":[
            {
                "type":"successresponce",
                "unconstructed":{
                    "valid": True,
                    "text": text,
                    "time":time.time()
                }
            }]
    }
    
    return {
        'statusCode': 200,
        'body': body
    }

def give_failure_response_body(text):
    
    body = {
        "messages":[
            {
                "type":"failure responce",
                "unconstructed":{
                    "valid": False,
                    "text": text,
                    "time":time.time()
                }
            }]
    }
    
    return {
        'statusCode': 200,
        'body': body
    }
    
    
    

