import boto3
from datetime import datetime

# Function to recognize a face and mark attendance
def recognize_face_and_mark_present(live_image_path):
    rekognition = boto3.client("rekognition", region_name="ap-south-1")  # AWS region
    dynamodb = boto3.client("dynamodb", region_name="ap-south-1")  # AWS region
    bucket_name = "ruthvik-bucket-mumbai"  # Replace with your S3 bucket name
    date = datetime.now().strftime("%Y-%m-%d")  # Attendance date
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Current timestamp

    try:
        # Search for matching faces in Rekognition
        response = rekognition.search_faces_by_image(
            CollectionId="students-collection",  # Your Rekognition face collection ID
            Image={"Bytes": open(live_image_path, "rb").read()},
            MaxFaces=1
        )
        
        if response["FaceMatches"]:
            roll_number = response["FaceMatches"][0]["Face"]["ExternalImageId"]  # Roll number as identifier
            
            # Mark the student as present in DynamoDB
            dynamodb.put_item(
                TableName="Attendance",
                Item={
                    "id": {"S": roll_number},
                    "date": {"S": date},
                    "status": {"S": "present"},
                    "timestamp": {"S": timestamp}
                }
            )
            print(f"Attendance marked present for {roll_number}")
            return roll_number
        else:
            print("No matching face found.")
            return None
    except Exception as e:
        print(f"Error recognizing face: {str(e)}")
        return None
