from flask import Flask, render_template
import boto3
from datetime import datetime
import csv
from openpyxl import Workbook
import os

app = Flask(__name__)

# Function to fetch class-level statistics for a specific date
def get_class_statistics(date):
    dynamodb = boto3.client("dynamodb", region_name="ap-south-1")
    try:
        response = dynamodb.query(
            TableName="attendance",
            KeyConditionExpression="id = :class_id",
            ExpressionAttributeValues={
                ":class_id": {"S": f"class-{date}"}
            }
        )
        if response.get("Items", []):
            item = response["Items"][0]
            return {
                "present": int(item.get("present_count", {}).get("N", 0)),
                "absent": int(item.get("absent_count", {}).get("N", 0))
            }
        else:
            return {"present": 0, "absent": 0}
    except Exception as e:
        print(f"Error fetching class statistics: {str(e)}")
        return {"present": 0, "absent": 0}

# Dashboard route to display attendance for today
@app.route("/")
def attendance_dashboard():
    date = datetime.now().strftime("%Y-%m-%d")
    stats = get_class_statistics(date)
    return render_template("dashboard.html", date=date, stats=stats)

# Dashboard route to filter attendance by a specific date
@app.route("/summary/<date>")
def attendance_summary(date):
    stats = get_class_statistics(date)
    return render_template("dashboard.html", date=date, stats=stats)

# CSV export route
@app.route("/export_csv")
def export_csv():
    try:
        export_attendance_to_csv()
        return "CSV export successful. Check attendance.csv in your directory."
    except Exception as e:
        return f"Error exporting CSV: {str(e)}"

# Excel export route
@app.route("/export_excel")
def export_excel():
    try:
        filename = export_attendance_to_excel()
        return f"Excel export successful. Check the file at: {filename}"
    except Exception as e:
        return f"Error exporting Excel: {str(e)}"

# Function to export attendance data to a CSV file
def export_attendance_to_csv():
    dynamodb = boto3.client("dynamodb", region_name="ap-south-1")
    try:
        response = dynamodb.scan(TableName="attendance")
        with open("attendance.csv", "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["ID", "Date", "Status", "Timestamp"])
            for item in response.get("Items", []):
                writer.writerow([
                    item["id"]["S"],
                    item["date"]["S"],
                    item["status"]["S"],
                    item["timestamp"]["S"]
                ])
        print("Attendance data exported to attendance.csv")
    except Exception as e:
        print(f"Error exporting attendance to CSV: {str(e)}")

# Updated function to export attendance data to an Excel file
def export_attendance_to_excel():
    dynamodb = boto3.client("dynamodb", region_name="ap-south-1")
    try:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Attendance"
        sheet.append(["ID", "Date", "Status", "Timestamp"])
        response = dynamodb.scan(TableName="attendance")
        for item in response.get("Items", []):
            # Handle missing fields gracefully
            id_field = item.get("id", {}).get("S", "unknown")
            date_field = item.get("date", {}).get("S", "unknown")
            status_field = item.get("status", {}).get("S", "unknown")
            timestamp_field = item.get("timestamp", {}).get("S", "unknown")
            sheet.append([id_field, date_field, status_field, timestamp_field])
        # Save Excel file with timestamped filename
        filename = os.path.join(os.getcwd(), f"attendance_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx")
        workbook.save(filename)
        print(f"Excel file successfully saved at: {filename}")
        return filename
    except Exception as e:
        print(f"Error exporting attendance to Excel: {str(e)}")
        raise

if __name__ == "__main__":
    app.run(debug=True)
