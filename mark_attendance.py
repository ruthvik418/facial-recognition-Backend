import boto3
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(filename="errors.log", level=logging.ERROR)

# Function to query user info from DynamoDB (validation step)
def get_user_info(user_id):
    dynamodb = boto3.client("dynamodb", region_name="ap-south-1")  # AWS region
    try:
        response = dynamodb.get_item(
            TableName="Users",  # Replace with your Users table name
            Key={"id": {"S": user_id}}
        )
        if "Item" in response:
            return response["Item"].get("name", {}).get("S", "Name Not Found")
        else:
            return "Unknown User"
    except Exception as e:
        logging.error(f"Error querying DynamoDB for user {user_id}: {str(e)}")
        return "Error"

# Function to mark individual student attendance
def mark_individual_attendance(roll_number, status):
    dynamodb = boto3.client("dynamodb", region_name="ap-south-1")  # AWS region
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Current timestamp
    date = datetime.now().strftime("%Y-%m-%d")  # Attendance date

    try:
        # Add individual attendance record to DynamoDB
        dynamodb.put_item(
            TableName="attendance",
            Item={
                "id": {"S": roll_number},
                "date": {"S": date},
                "status": {"S": status},
                "timestamp": {"S": timestamp}
            }
        )
        print(f"Attendance marked for {roll_number}: {status} on {date}")
    except Exception as e:
        logging.error(f"Error marking individual attendance for {roll_number}: {str(e)}")
        print(f"Error marking individual attendance: {str(e)}")

# Function to update class-level attendance statistics
def update_class_statistics(status):
    dynamodb = boto3.client("dynamodb", region_name="ap-south-1")  # AWS region
    date = datetime.now().strftime("%Y-%m-%d")  # Attendance date

    try:
        # Fetch existing class-level record
        response = dynamodb.get_item(
            TableName="attendance",
            Key={
                "id": {"S": f"class-{date}"},
                "date": {"S": date}
            }
        )

        # Check if the record exists and update counts accordingly
        if "Item" in response:
            present_count = int(response["Item"]["present_count"]["N"])
            absent_count = int(response["Item"]["absent_count"]["N"])
            
            if status == "present":
                present_count += 1
            else:
                absent_count += 1

            # Update the class-level record
            dynamodb.put_item(
                TableName="attendance",
                Item={
                    "id": {"S": f"class-{date}"},
                    "date": {"S": date},
                    "present_count": {"N": str(present_count)},
                    "absent_count": {"N": str(absent_count)}
                }
            )
        else:
            # Initialize class-level record if not exists
            dynamodb.put_item(
                TableName="attendance",
                Item={
                    "id": {"S": f"class-{date}"},
                    "date": {"S": date},
                    "present_count": {"N": "1" if status == "present" else "0"},
                    "absent_count": {"N": "1" if status == "absent" else "0"}
                }
            )
        print(f"Class statistics updated for {date}.")
    except Exception as e:
        logging.error(f"Error updating class statistics for {date}: {str(e)}")
        print(f"Error updating class statistics: {str(e)}")

# Combined function to handle attendance marking
def mark_attendance(user_id, status):
    dynamodb = boto3.client("dynamodb", region_name="ap-south-1")  # AWS region
    
    # Validate user existence
    user_name = get_user_info(user_id)
    if user_name == "Unknown User" or user_name == "Error":
        print(f"Cannot mark attendance: User {user_id} not found.")
        return

    # Mark individual attendance
    mark_individual_attendance(user_id, status)
    
    # Update class-level statistics
    update_class_statistics(status)

def mark_absentees():
    dynamodb = boto3.client("dynamodb", region_name="ap-south-1")
    date = datetime.now().strftime("%Y-%m-%d")
    
    try:
        # Fetch all students from the Users table
        users_response = dynamodb.scan(TableName="Users")
        all_students = [item["id"]["S"] for item in users_response["Items"]]
        
        # Fetch students already marked as present
        attendance_response = dynamodb.scan(
            TableName="attendance",
            FilterExpression="date = :d AND status = :s",
            ExpressionAttributeValues={
                ":d": {"S": date},
                ":s": {"S": "present"}
            }
        )
        present_students = [item["id"]["S"] for item in attendance_response["Items"]]
        
        # Find absentees by subtracting present students from all students
        absentees = set(all_students) - set(present_students)
        for roll_number in absentees:
            dynamodb.put_item(
                TableName="attendance",
                Item={
                    "id": {"S": roll_number},
                    "date": {"S": date},
                    "status": {"S": "absent"},
                    "timestamp": {"S": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                }
            )
            print(f"Marked absent: {roll_number}")
    except Exception as e:
        print(f"Error marking absentees: {str(e)}")

def process_all_images(bucket_name, collection_id):
    rekognition = boto3.client("rekognition", region_name="ap-south-1")
    s3 = boto3.client("s3")

    # List all images in the S3 bucket
    response = s3.list_objects_v2(Bucket=bucket_name)
    for obj in response.get("Contents", []):
        image_name = obj["Key"]
        try:
            response = rekognition.search_faces_by_image(
                CollectionId=collection_id,
                Image={"S3Object": {"Bucket": bucket_name, "Name": image_name}},
                MaxFaces=1
            )
            if response["FaceMatches"]:
                user_id = response["FaceMatches"][0]["Face"]["ExternalImageId"]
                mark_attendance(user_id, "present")
            else:
                print(f"No face match for {image_name}")
        except Exception as e:
            print(f"Error processing {image_name}: {str(e)}")

def send_email(student_email, subject, body):
    ses = boto3.client("ses", region_name="ap-south-1")
    try:
        response = ses.send_email(
            Source="your-email@example.com",
            Destination={"ToAddresses": [student_email]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": body}}
            }
        )
        print(f"Email sent to {student_email}")
    except Exception as e:
        print(f"Error sending email: {str(e)}")

def send_sms(phone_number, message):
    sns = boto3.client("sns", region_name="ap-south-1")
    try:
        response = sns.publish(
            PhoneNumber=phone_number,
            Message=message
        )
        print(f"SMS sent to {phone_number}")
    except Exception as e:
        print(f"Error sending SMS: {str(e)}")

process_all_images("ruthvik-bucket-mumbai ", "students-collection")
