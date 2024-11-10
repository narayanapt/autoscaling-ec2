import boto3
import torch
from torchvision import transforms
from PIL import Image
import base64
import io
from facenet_pytorch import MTCNN, InceptionResnetV1
import os
import numpy as np


# AWS SQS and S3 setup
sqs = boto3.client(
    'sqs',
    region_name='us-east-1',
    
)

s3 = boto3.client(
    's3',
    region_name='us-east-1',
    
)
# Replace with your actual SQS queue URLs and S3 bucket names
REQUEST_QUEUE_URL = ''
RESPONSE_QUEUE_URL = ''
INPUT_BUCKET_NAME = ''
OUTPUT_BUCKET_NAME = ''


# Load the pre-trained face recognition model (adjust as needed)
mtcnn = MTCNN(image_size=240, margin=0, min_face_size=20)  # Face detection
resnet = InceptionResnetV1(pretrained='vggface2').eval()  # Face embedding extraction

saved_data = torch.load('/home/ubuntu/App/model/data.pt')  
embedding_list = saved_data[0]  
name_list = saved_data[1]  

def classify_image(image_data):
    
    image_bytes = base64.b64decode(image_data)  # Decode base64 to bytes
    image = Image.open(io.BytesIO(image_bytes)).convert('RGB')  # Load image and convert to RGB
    

    face, prob = mtcnn(image, return_prob=True)  # returns cropped face and probability
    if face is None:
        return ("No face detected", None)  # If no face is detected, return this message
    
    emb = resnet(face.unsqueeze(0)).detach()  # Generate embedding and detach gradients
    dist_list = []  
    
    for idx, emb_db in enumerate(embedding_list):
        dist = torch.dist(emb, emb_db).item()  # Calculate Euclidean distance between embeddings
        dist_list.append(dist)

    idx_min = dist_list.index(min(dist_list))  # Get the index of the smallest distance

    return (name_list[idx_min], min(dist_list))


def handle_message():
    """ Fetch, process, and deduplicate messages from the Request Queue. """
    try:
        response = sqs.receive_message(
            QueueUrl=REQUEST_QUEUE_URL,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=10,
            MessageAttributeNames=['All']
        )

        if 'Messages' in response:
            message = response['Messages'][0]
            receipt_handle = message['ReceiptHandle']

            # Extract the Request ID and filename
            request_id = message['MessageAttributes']['RequestId']['StringValue']
            filename = message['MessageAttributes']['FileName']['StringValue']
            image_data = message['Body']

            print(filename)


            upload_to_s3(INPUT_BUCKET_NAME, filename, image_data)

            result = classify_image(image_data)

            print(result)

            upload_to_s3(OUTPUT_BUCKET_NAME, filename.split('.')[0], result[0])

            sqs.send_message(
                QueueUrl=RESPONSE_QUEUE_URL,
                MessageAttributes={
                    'RequestId': {
                        'DataType': 'String',
                        'StringValue': request_id
                    }
                },
                MessageBody=f"{filename.split('.')[0]}:{result[0]}"
            )

            print(f"{filename.split('.')[0]}:{result[0]}")

            sqs.delete_message(QueueUrl=REQUEST_QUEUE_URL, ReceiptHandle=receipt_handle)
            print(f"Processed and deleted message for file: {filename}")

    except Exception as e:
        print(f"Error processing message: {str(e)}")

def upload_to_s3(bucket_name, key, data):
    """ Upload data (image or result) to S3. """
    try:
        if key.endswith(".jpg"):
            s3.put_object(Bucket=bucket_name, Key=key, Body=base64.b64decode(data))
        else:
            s3.put_object(Bucket=bucket_name, Key=key, Body=data)
        print(f"Uploaded {key} to S3 bucket {bucket_name}")
    except Exception as e:
        print(f"Error uploading {key} to S3: {str(e)}")

if __name__ == '__main__':
    print("App Tier started, waiting for messages...")
    while True:
        handle_message()
