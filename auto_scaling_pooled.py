import boto3
import time

# Configuration
REQUEST_QUEUE_NAME = ''
MAX_INSTANCES = 20  # Total instances to manage
MIN_INSTANCES = 0
SCALE_UP_THRESHOLD = 1   # Scale up if more than this many messages in the queue
SCALE_DOWN_THRESHOLD = 0 # Scale down if less than this many messages in the queue

# AWS clients
sqs = boto3.client('sqs', region_name='us-east-1')
ec2 = boto3.client('ec2', region_name='us-east-1')

# List of EC2 instance IDs for the App Tier
INSTANCE_POOL = []

def get_queue_length(queue_name):
    # Get SQS queue URL
    queue_url = sqs.get_queue_url(QueueName=queue_name)['QueueUrl']
    
    # Get the attributes of the queue
    attributes = sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=['ApproximateNumberOfMessages'])
    return int(attributes['Attributes']['ApproximateNumberOfMessages'])

def get_running_instances():
    # Get currently running App Tier instances
    instances = ec2.describe_instances(
        Filters=[
            {'Name': 'instance-id', 'Values': INSTANCE_POOL},
            {'Name': 'instance-state-name', 'Values': ['running']}
        ]
    )
    return instances['Reservations']

def get_stopped_instances():
    # Get currently stopped instances
    instances = ec2.describe_instances(
        Filters=[
            {'Name': 'instance-id', 'Values': INSTANCE_POOL},
            {'Name': 'instance-state-name', 'Values': ['stopped']}
        ]
    )
    return instances['Reservations']

def start_instance(instance_id):
    # Start an instance
    ec2.start_instances(InstanceIds=[instance_id])
    print(f"Started instance {instance_id}.")

def stop_instance(instance_id):
    # Stop an instance
    ec2.stop_instances(InstanceIds=[instance_id])
    print(f"Stopped instance {instance_id}.")

def purge_output_queue(queue_url):
    """Purges the output queue."""
    try:
        sqs.purge_queue(QueueUrl=queue_url)
        print(f"Purged output queue: {queue_url}")
    except Exception as e:
        print(f"Error purging output queue: {e}")

def get_queue_length(queue_name):
    """Get the number of messages in a queue."""
    queue_url = sqs.get_queue_url(QueueName=queue_name)['QueueUrl']
    attributes = sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=['ApproximateNumberOfMessages'])
    return int(attributes['Attributes']['ApproximateNumberOfMessages'])

def purge_output_queue(queue_url):
    """Purges the output queue if it has messages."""
    try:
        # Get the length of the output queue
        output_queue_length = get_queue_length('')
        
        if output_queue_length > 0:
            sqs.purge_queue(QueueUrl=queue_url)
            print(f"Purged output queue: {queue_url}")
    
    except Exception as e:
        print(f"Error purging output queue: {e}")

def autoscale():
    while True:
        try:
            # Get the current queue length and running instances
            queue_length = get_queue_length(REQUEST_QUEUE_NAME)
            running_instances = get_running_instances()
            stopped_instances = get_stopped_instances()
            num_running = len(running_instances)  # Running instances from the pool
            num_stopped = len(stopped_instances)

            print(f"Queue length: {queue_length}, Running instances: {num_running}, Stopped instances: {num_stopped}")

            # If no instances are running, check the output queue length and purge if necessary
            if num_running == 0:
                OUTPUT_QUEUE_URL = ''
                purge_output_queue(OUTPUT_QUEUE_URL)

            # Scale up if needed (start instances to match the target number of instances)
            target_instances = min(queue_length, MAX_INSTANCES)
            if target_instances > num_running and num_running < MAX_INSTANCES:
                instances_to_start = min(target_instances - num_running, num_stopped)
                
                # Start instances in order
                stopped_instance_ids = sorted([instance['Instances'][0]['InstanceId'] for instance in stopped_instances], key=lambda x: INSTANCE_POOL.index(x))
                instances_to_start_list = stopped_instance_ids[:instances_to_start]
                
                for instance_id in instances_to_start_list:
                    start_instance(instance_id)

            # Scale down if needed (stop 2 running instances at a time)
            elif target_instances < num_running and num_running > MIN_INSTANCES:
                # Stop 2 instances at a time
                instances_to_stop = min(2, num_running - MIN_INSTANCES)
                running_instance_ids = sorted([instance['Instances'][0]['InstanceId'] for instance in running_instances], key=lambda x: INSTANCE_POOL.index(x), reverse=True)
                instances_to_stop_list = running_instance_ids[:instances_to_stop]
                
                for instance_id in instances_to_stop_list:
                    stop_instance(instance_id)

        except Exception as e:
            print(f"Error during autoscaling: {e}")
        
        time.sleep(5)  # Check every 5 seconds



if __name__ == "__main__":
    autoscale()

