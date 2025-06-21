from flask import Flask, request, jsonify, render_template, session, redirect, url_for, Response
import boto3
import datetime as dt
from datetime import datetime, timedelta, timezone
import pytz
from boto3.dynamodb.conditions import Key
from shapely.geometry import Point
import logging
import os
import bcrypt
from io import BytesIO, StringIO
import csv
import math
import os
from collections import defaultdict

now = datetime.now()        # Uses the class
mod_now = dt.datetime.now() # Uses the module's class explicitly

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")
# Basic logging
logging.basicConfig(level=logging.INFO)

# ----------------------
# AWS Configuration
# ----------------------
dynamodb = boto3.resource("dynamodb")
students_table = dynamodb.Table("Students-Table")
teachers_table = dynamodb.Table("Teachers-Table")
attendance_table = dynamodb.Table("attendance")  # For attendance records

s3 = boto3.client("s3")
rekognition = boto3.client("rekognition")
ses = boto3.client("ses", region_name="us-east-1")  # Update region as needed
S3_BUCKET = "ruthvik-bucket-mumbai"
REKOGNITION_COLLECTION = "students-collection"

CAMPUS_LAT = 17.384    # Example campus latitude
CAMPUS_LON = 78.456    # Example campus longitude
ALLOWED_RADIUS_KM = 200.0

# ----------------------
# Helper Functions
# ----------------------
def get_request_data():
    if request.is_json:
        return request.get_json()
    else:
        return request.form
    
    from shapely.geometry import Point

def is_within_campus(lat, lon, campus_lat, campus_lon, radius_km):
    # Convert radius from kilometers to degrees (approximate conversion)
    buffer_radius = radius_km / 111.0  
    
    campus_center = Point(campus_lon, campus_lat)  # (x, y) order
    user_point = Point(lon, lat)
    
    # campus_center.buffer(buffer_radius) creates a circular polygon around the campus center.
    return user_point.within(campus_center.buffer(buffer_radius))

def send_sms(phone_number, message):
    try:
        # Import and load necessary environment variables
        from twilio.rest import Client
        import os
        from dotenv import load_dotenv

        # Load environment variables from .env file
        load_dotenv()
        
        # Retrieve Twilio credentials
        TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
        TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
        TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")  # Or Messaging Service SID if using one

        # Validate that the Twilio credentials are loaded
        if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER):
            logging.error("Twilio credentials are missing. Ensure that .env is correctly configured.")
            return

        # Initialize the Twilio client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        # Log the SMS sending attempt
        logging.info(f"Attempting to send SMS to {phone_number}")

        # Send the SMS
        message_response = client.messages.create(
            to=phone_number,
            from_=TWILIO_PHONE_NUMBER,  # Replace with 'messaging_service_sid' if using that
            body=message
        )

        # Log the successful SMS response
        logging.info(f"SMS sent successfully to {phone_number}. Message SID: {message_response.sid}")

    except Exception as e:
        # Log any errors encountered
        logging.error(f"Failed to send SMS to {phone_number}: {e}")


# ----------------------
# Home Endpoint
# ----------------------
@app.route("/")
def home():
    return render_template("home.html")

# ----------------------
# 1. Registration Endpoint (Students/Teachers)
# ----------------------

@app.route("/register/<role>", methods=["GET", "POST"])
def register(role):
    if request.method == "GET":
        return render_template("register.html", role=role)

    try:
        # Generate current time in IST
        IST = pytz.timezone('Asia/Kolkata')
        current_ist_time = datetime.now(IST)
        
        user_id = request.form["id"]
        email = request.form["email"]
        password = request.form["password"]
        hashed_pw = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        if role == "student":
            user_class = request.form["class"]
            phone_number = request.form.get("phone")  # Retrieve phone number from form

            # Validate phone number
            if not phone_number:
                return jsonify({"message": "Phone number is required for student registration."}), 400
            if not phone_number.isdigit() or len(phone_number) != 10:
                return jsonify({"message": "Invalid phone number format. Please provide a valid 10-digit number."}), 400
            
            # Validate face image
            if "face_image" not in request.files:
                return jsonify({"message": "Face image is required for student registration."}), 400

            face_image_file = request.files["face_image"]
            file_data = face_image_file.read()
            if not file_data:
                logging.error("Uploaded file is empty.")
                return jsonify({"message": "Uploaded file is empty."}), 400

            # Save the face image to S3
            filename = f"faces/{user_id}_capture.png"
            try:
                s3.put_object(Bucket=S3_BUCKET, Key=filename, Body=file_data)
            except Exception as s3_error:
                logging.error("S3 upload error: %s", s3_error, exc_info=True)
                return jsonify({"message": "Failed to upload image to S3."}), 500

            s3_url = f"https://{S3_BUCKET}.s3.amazonaws.com/{filename}"

            # Index the face into Rekognition’s collection
            try:
                rekognition_response = rekognition.index_faces(
                    CollectionId=REKOGNITION_COLLECTION,
                    Image={"S3Object": {"Bucket": S3_BUCKET, "Name": filename}},
                    ExternalImageId=user_id,  # Use student ID as ExternalImageId
                    DetectionAttributes=["DEFAULT"]
                )
            except Exception as index_error:
                logging.error("Error indexing face with Rekognition: %s", index_error, exc_info=True)
                return jsonify({"message": "Failed to index face in Rekognition."}), 500

            # Check if Rekognition detected a valid face
            face_records = rekognition_response.get("FaceRecords", [])
            if not face_records:
                return jsonify({"message": "Face not found in the uploaded image. Please try again with a clear photo of your face."}), 400

            # Save student data into DynamoDB with IST timestamp
            students_table.put_item(
                Item={
                    "id": user_id,
                    "name": request.form["name"],
                    "email": email,
                    "class": user_class,
                    "phone_number": phone_number,
                    "password_hash": hashed_pw,
                    "username": request.form["name"],
                    "face_image_url": s3_url,
                    "registered_at": current_ist_time.strftime("%Y-%m-%d %H:%M:%S %Z")
                }
            )
            logging.info(f"Student registered: {user_id} at {current_ist_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            return jsonify({"message": "Student registration successful!", "s3_url": s3_url})

        elif role == "teacher":
            subject = request.form["subject"]
            # Save teacher data into DynamoDB with IST timestamp
            teachers_table.put_item(
                Item={
                    "id": user_id,
                    "name": request.form["name"],
                    "email": email,
                    "subject": subject,
                    "password_hash": hashed_pw,
                    "username": request.form["name"],
                    "registered_at": current_ist_time.strftime("%Y-%m-%d %H:%M:%S %Z")
                }
            )
            logging.info(f"Teacher registered: {user_id} at {current_ist_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            return jsonify({"message": "Teacher registration successful!"})

        else:
            return jsonify({"message": "Invalid role provided."}), 400

    except Exception as e:
        logging.error("Error during registration:", exc_info=True)
        return jsonify({"message": "An error occurred during registration."}), 500

# ----------------------
# 2. Login Endpoint (Students/Teachers)
# ----------------------
@app.route("/login/<role>", methods=["GET", "POST"])
def login(role):
    if request.method == "GET":
        return render_template("login.html", role=role)

    try:
        user_id = request.form["id"]
        password = request.form["password"]

        if role == "student":
            response = students_table.get_item(Key={"id": user_id})
            if "Item" not in response:
                return render_template("login.html", role=role, error="Invalid credentials.")
            user = response["Item"]
        elif role == "teacher":
            response = teachers_table.get_item(Key={"id": user_id})
            if "Item" not in response:
                return render_template("login.html", role=role, error="Invalid credentials.")
            user = response["Item"]
        else:
            return render_template("login.html", role=role, error="Invalid role.")

        if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
            return render_template("login.html", role=role, error="Invalid credentials.")

        session["user_id"] = user_id
        session["role"] = role
        session["username"] = user["username"]

        return redirect(url_for("dashboard"))

    except Exception as e:
        logging.error("Error during login:", exc_info=True)
        return render_template("login.html", role=role, error="An error occurred during login. Please try again.")

# ----------------------
# Unified Dashboard Route
# ----------------------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session or "role" not in session:
        return redirect(url_for("login"))
    if session["role"] == "teacher":
        return redirect(url_for("teacher_dashboard"))
    else:
        return redirect(url_for("student_dashboard"))

# ----------------------
# Teacher Dashboard
# ----------------------
@app.route("/teacher_dashboard")
def teacher_dashboard():
    if session.get("role") != "teacher":
        return redirect(url_for("dashboard"))
    
    username = session.get("username")
    
    # Fetch attendance data for trends (e.g., count of 'Present' per date)
    attendance_response = attendance_table.scan()
    records = attendance_response.get("Items", [])
    trends = {}
    for record in records:
        if record.get("status") == "Present":
            date = record.get("date")
            trends[date] = trends.get(date, 0) + 1
    
    # Sort trends data by date
    sorted_trends = sorted(trends.items())
    trend_labels = [date for date, count in sorted_trends]
    attendance_counts = [count for date, count in sorted_trends]
    
    # Render template with trend data
    return render_template(
        "teacher_dashboard.html", 
        username=username, 
        trend_labels=trend_labels, 
        attendance_counts=attendance_counts
    )

# ----------------------
# Student Dashboard
# ----------------------
@app.route("/student_dashboard")
def student_dashboard():
    if session.get("role") != "student":
        return redirect(url_for("dashboard"))
    
    username = session.get("username")
    student_id = session.get("user_id")
    app.logger.info("Student id from session: %s", student_id)

    # Calculate the current month's start and end dates
    now = datetime.now()  # current time

    start_date = datetime(now.year, now.month, 1)
    if now.month == 12:
        start_of_next_month = datetime(now.year + 1, 1, 1)
    else:
        start_of_next_month = datetime(now.year, now.month + 1, 1)
    # Ensure timedelta is imported: from datetime import timedelta
    end_date = start_of_next_month - timedelta(days=1)
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")

    app.logger.info("Date range - Start: %s, End: %s", start_date_str, end_date_str)

    # Query using the index (Option 1)
    try:
        response = attendance_table.query(
            IndexName="student_id-index",  # Ensure this index exists
            KeyConditionExpression=Key("student_id").eq(student_id) & Key("date").between(start_date_str, end_date_str)
        )
        attendance_records = response.get("Items", [])
    except Exception as e:
        logging.error("Error querying attendance table with index: %s", e)
        attendance_records = []

    # Backup query using the table's primary keys (Option 2)
    try:
        if not attendance_records:  # Only query without the index if the above fails
            response = attendance_table.query(
                KeyConditionExpression=Key("id").eq(student_id) & Key("date").between(start_date_str, end_date_str)
            )
            attendance_records = response.get("Items", [])
    except Exception as e:
        logging.error("Error querying attendance table with primary keys: %s", e)
        attendance_records = []

    # Count 'present' records for the current month
    present_count = 1
    for record in attendance_records:
        try:
            record_date = datetime.strptime(record.get("date", "0001-01-01"), "%Y-%m-%d")
            if record.get("status", "").lower() == "present" and record_date.month == now.month:
                present_count += 1
        except Exception as e:
            logging.error("Error processing record %s: %s", record, e)

    chart_data = {
        "labels": ["This Month"],
        "data": [present_count]
    }

    return render_template("student_dashboard.html",
                           username=username,
                           attendance_records=attendance_records,
                           chart_data=chart_data)

# ----------------------
# 4. Attendance Marking Endpoint (Using Geohashing)
# ----------------------

@app.route("/mark_attendance", methods=["GET", "POST"])
def mark_attendance():
    if "user_id" not in session or session.get("role") != "student":
        return redirect(url_for("login"))

    if request.method == "GET":
        username = session.get("username")  # Fetch username from session
        return render_template("attendance.html", username=username)  # Pass username to the template

    try:
        # Use the imported timezone and timedelta as is.
        current_time = datetime.now(timezone.utc)
        one_hour_ago = current_time - timedelta(hours=1)
        start_date_str = one_hour_ago.strftime("%Y-%m-%d")  # Define start date
        end_date_str = current_time.strftime("%Y-%m-%d")  # Define end date

        # Validate that a face image was uploaded.
        if "face_image" not in request.files:
            return jsonify({"message": "Face image is required for attendance."}), 400

        # Retrieve geolocation fields.
        lat_str = request.form.get("lat")
        lon_str = request.form.get("lon")
        if not lat_str or not lon_str:
            return jsonify({"message": "Geolocation data is missing."}), 400

        try:
            user_lat = float(lat_str)
            user_lon = float(lon_str)
        except ValueError:
            return jsonify({"message": "Invalid geolocation data."}), 400

        # Validate the user is on campus.
        if not is_within_campus(user_lat, user_lon, CAMPUS_LAT, CAMPUS_LON, ALLOWED_RADIUS_KM):
            return jsonify({"message": "You are not on campus. Attendance cannot be marked."}), 403

        # Read the uploaded file.
        face_image_file = request.files["face_image"]
        file_data = face_image_file.read()
        if not file_data:
            return jsonify({"message": "Uploaded file is empty."}), 400

        # Use AWS Rekognition to search for matching faces.
        try:
            search_response = rekognition.search_faces_by_image(
                CollectionId=REKOGNITION_COLLECTION,
                Image={"Bytes": file_data},
                FaceMatchThreshold=80,
                MaxFaces=10  # Allow up to 10 face matches
            )
        except Exception as rekognition_error:
            logging.error("Error during Rekognition search: %s", rekognition_error, exc_info=True)
            return jsonify({"message": "Error during face search. Please try again."}), 500

        if not search_response.get("FaceMatches"):
            return jsonify({"message": "No registered faces matched in the image."}), 401

        recognized_students = set()  # To store unique recognized student IDs
        logged_in_student_id = session.get("user_id")

        # Iterate over all matched faces
        for face_match in search_response["FaceMatches"]:
            student_id = face_match["Face"].get("ExternalImageId")
            if student_id and student_id not in recognized_students:  # Only update once per student ID
                # Check if the student marked attendance within the last hour
                response = attendance_table.query(
                    IndexName="student_id-index",  # Ensure this index exists
                    KeyConditionExpression=Key("student_id").eq(student_id) & Key("date").between(start_date_str, end_date_str),
                    ScanIndexForward=False,  # Sort in descending order (latest first)
                    Limit=1  # Only fetch the most recent attendance record
                )
                last_attendance = response.get("Items", [])
                if last_attendance:
                    last_timestamp = datetime.strptime(
                        last_attendance[0]["timestamp"], "%Y-%m-%dT%H:%M:%S.%f%z"
                    )
                    if last_timestamp > one_hour_ago:
                        # Customized error message for attendance within 1 hour
                        return jsonify({
                            "message": "You have already marked attendance. Please try again after 1 hour."
                        }), 403

                # Mark attendance for the recognized student
                timestamp = current_time.isoformat()
                date = current_time.strftime("%Y-%m-%d")
                attendance_item = {
                    "id": f"{student_id}_{timestamp}",
                    "student_id": student_id,
                    "timestamp": timestamp,
                    "date": date,
                    "status": "Present"
                }
                attendance_table.put_item(Item=attendance_item)
                recognized_students.add(student_id)  # Add to the set to prevent duplicate updates

                # Update attendance count for the student
                student_response = students_table.get_item(Key={"id": student_id})
                if "Item" in student_response:
                    student = student_response["Item"]
                    current_count = student.get("attendance_count", 0)  # Defaults to 0 if no count exists
                    updated_count = current_count + 1  # Increment the count
                    students_table.update_item(
                        Key={"id": student_id},
                        UpdateExpression="SET attendance_count = :count",
                        ExpressionAttributeValues={":count": updated_count}
                    )

                    # Send SMS notification to the student
                    phone_number = student.get("phone_number")
                    student_name = student.get("name")
                    if phone_number and phone_number.isdigit() and len(phone_number) == 10:
                        formatted_phone_number = f"+91{phone_number}"
                        message = f"Hi {student_name}, your attendance has been successfully marked on {date} at {current_time.strftime('%H:%M:%S')}."
                        send_sms(formatted_phone_number, message)


        # Check if no students were recognized
        if not recognized_students:
            return jsonify({"message": "No registered faces matched in the image."}), 401

        return jsonify({
            "message": "Attendance marked successfully for all recognized students.",
            "marked_students": list(recognized_students)
        })

    except Exception as e:
        logging.error("Error during attendance marking:", exc_info=True)
        return jsonify({"message": "Error during attendance marking."}), 500

# ----------------------
# 5. Attendance Summary Dashboard (Teacher-only)
# ----------------------

@app.route("/attendance_summary", methods=["GET"])
def attendance_summary():
    # Only allow teacher access.
    if "user_id" not in session or session.get("role") != "teacher":
        return redirect(url_for("login", role="teacher"))
    
    # Get today's date in UTC
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    # Retrieve all attendance records
    response = attendance_table.scan()
    records = response.get("Items", [])
    
    # Augment records with the student's name
    student_response = students_table.scan()
    student_mapping = {student["id"].lower(): student.get("name", "N/A") for student in student_response.get("Items", [])}
    
    for record in records:
        student_id = record.get("student_id", "").lower()
        record["name"] = record.get("name") or student_mapping.get(student_id, "N/A")
    
    # Aggregate attendance counts per date
    summary = {}
    for record in records:
        record_date = record.get("date")
        if record_date:
            summary[record_date] = summary.get(record_date, 0) + 1
    
    # Sort summary with today at the top
    sorted_summary = {today: summary.get(today, 0)}  # Start with today
    for date in sorted(summary.keys()):
        if date != today:
            sorted_summary[date] = summary[date]
    
    # Filter today's records for detailed view
    detailed_today = [record for record in records if record.get("date") == today]

    # Render the template
    return render_template(
        "attendance_summary.html",
        summary=sorted_summary,
        detailed_today=detailed_today
    )

# ----------------------
# 6. CSV Export Endpoint (Teacher-only)
# ----------------------
@app.route("/export_attendance", methods=["GET"])
def export_attendance():
    if "user_id" not in session or session.get("role") != "teacher":
        return redirect(url_for("login", role="teacher"))
    
    response = attendance_table.scan()
    records = response.get("Items", [])
    
    si = StringIO()
    csv_writer = csv.writer(si)
    header = ["id", "student_id", "timestamp", "date", "status"]
    csv_writer.writerow(header)
    for record in records:
        csv_writer.writerow([
            record.get("id", ""),
            record.get("student_id", ""),
            record.get("timestamp", ""),
            record.get("date", ""),
            record.get("status", "")
        ])
    output = si.getvalue()
    si.close()
    
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=attendance_records.csv"}
    )

# ----------------------
# 7. Logout Endpoint
# ----------------------
@app.route('/logout')
def logout_user():
    role = session.get("role", "teacher")  # Default to "teacher" if no role is set
    session.clear()
    return redirect(url_for('login', role=role))

@app.route("/dashboard_data", methods=["GET"])
def dashboard_data():
    try:
        # Step 1: Retrieve all attendance records from the database
        response = attendance_table.scan()  # Replace with your table scan logic
        records = response.get("Items", [])

        # Step 2: Get the requested time range (daily, weekly, monthly) from query parameters
        time_range = request.args.get("range", "daily")  # Default to daily if no range is provided

        # Step 3: Aggregate attendance data based on the requested range
        attendance_summary = defaultdict(int)
        for record in records:
            if record.get("status") == "Present":  # Filter records for "Present" status
                attendance_date = record.get("date")  # Expected format: 'YYYY-MM-DD'

                if time_range == "daily":
                    # Aggregate by exact date (daily)
                    attendance_summary[attendance_date] += 1
                elif time_range == "weekly":
                    # Aggregate by ISO week number
                    week_number = datetime.strptime(attendance_date, "%Y-%m-%d").isocalendar()[1]
                    attendance_summary[f"Week {week_number}"] += 1
                elif time_range == "monthly":
                    # Aggregate by month (YYYY-MM format)
                    month = attendance_date[:7]  # Extract 'YYYY-MM'
                    attendance_summary[month] += 1

        # Step 4: Sort aggregated data for proper chart rendering
        sorted_keys = sorted(attendance_summary.keys())  # E.g., ['2025-04-23', '2025-04-24', ...] for daily
        trend_labels = sorted_keys
        attendance_trend = [attendance_summary[key] for key in sorted_keys]

        # Step 5: Return aggregated data as JSON
        return jsonify({
            "trendLabels": trend_labels,  # Dates, weeks, or months
            "attendanceTrend": attendance_trend  # Number of students marked "Present" for each period
        })

    except Exception as e:
        app.logger.error(f"Error in /dashboard_data: {e}")
        return jsonify({"error": "Failed to load data"}), 500

if __name__ == "__main__":
    app.run(debug=True)
