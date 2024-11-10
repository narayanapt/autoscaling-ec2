import boto3
import uuid
import base64
from flask import Flask, request, jsonify

app = Flask(__name__)

# AWS SQS setup
sqs = boto3.client('sqs', region_name='us-east-1')

# Replace with your actual SQS queue URLs
REQUEST_QUEUE_URL = ''
RESPONSE_QUEUE_URL = ''

tracked_requests = {}

@app.route('/', methods=['POST'])
def recognize_face():
    # Check if 'inputFile' is in the POST request
    if 'inputFile' not in request.files:
        return jsonify({"error": "No inputFile part in the request"}), 400

    # Retrieve the uploaded file
    file = request.files['inputFile']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Generate a unique Request ID for the request
    
    filename = file.filename
    request_id = str(uuid.uuid4())


    # Encode the image file to base64 string for sending via SQS
    image_data = base64.b64encode(file.read()).decode('utf-8')

    try:
        # Send the image and Request ID to the Request Queue
        sqs.send_message(
            QueueUrl=REQUEST_QUEUE_URL,
            MessageAttributes={
                'RequestId': {
                    'DataType': 'String',
                    'StringValue': request_id
                },
                'FileName': {
                    'DataType': 'String',
                    'StringValue': filename
                }
            },
            MessageBody=image_data
            
        )

        # Store the request ID to track the response later
        tracked_requests[request_id] = filename

        # Poll the Response Queue for the result of this Request ID
        while True:
            response = sqs.receive_message(
                QueueUrl=RESPONSE_QUEUE_URL,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=10,
                MessageAttributeNames=['All']
            )

            if 'Messages' in response:
                message = response['Messages'][0]
                receipt_handle = message['ReceiptHandle']

                # Extract the Request ID and result
                response_request_id = message['MessageAttributes']['RequestId']['StringValue']
                result = message['Body']
                # print(f"response request id : {response_request_id}")

                # Check if this response corresponds to the current request
                if response_request_id == request_id:
                    # Delete the message after processing
                    sqs.delete_message(
                        QueueUrl=RESPONSE_QUEUE_URL,
                        ReceiptHandle=receipt_handle
                    )
                    print(f"deleted request-id: {request_id}")
                    return result


    except Exception as e:
        return jsonify({"error": f"Failed to send message to request queue: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True)

