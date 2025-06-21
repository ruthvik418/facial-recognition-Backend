import boto3

# Function to upload face to S3
def upload_face_to_s3(file_path, user_id):
    s3 = boto3.client("s3", region_name="ap-south-1")  # Replace with your AWS region
    bucket_name = "ruthvik-bucket-mumbai"  # Your S3 bucket name
    
    try:
        # Upload the face image with the user_id as the file name
        s3.upload_file(file_path, bucket_name, f"{user_id}.jpg")
        s3_url = f"s3://{bucket_name}/{user_id}.jpg"
        print(f"Uploaded face to S3: {s3_url}")
        return s3_url
    except Exception as e:
        print(f"Error uploading to S3: {str(e)}")
        return None

# Function to register user in DynamoDB
def register_user_in_dynamodb(user_id, name, s3_url):
    dynamodb = boto3.client("dynamodb", region_name="ap-south-1")  # Replace with your AWS region
    try:
        dynamodb.put_item(
            TableName="student-attendance",  # Replace with your DynamoDB table name
            Item={
                "id": {"S": user_id},
                "name": {"S": name},
                "face_reference": {"S": s3_url}
            }
        )
        print(f"User registered: {user_id} - {name}")
    except Exception as e:
        print(f"Error registering user in DynamoDB: {str(e)}")

# Main registration workflow
def register_user(file_path, user_id, name):
    # Upload the face image to S3
    s3_url = upload_face_to_s3(file_path, user_id)
    if s3_url:
        # Save user data in DynamoDB
        register_user_in_dynamodb(user_id, name, s3_url)
    else:
        print("Failed to register user due to S3 upload error.")

# Example usage
if __name__ == "__main__":
    file_path = "ruthvik.jpg"  # Path to the image
    user_id = "23241A0542"  # Example user ID
    name = "Parasu Jaya Ruthvik"  # User's name
    register_user(file_path, user_id, name)
