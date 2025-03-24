import cv2
import face_recognition
import numpy as np
import os
from datetime import datetime
from flask import Flask, render_template, jsonify, request, redirect, url_for, session
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import sqlite3
import base64
import threading
import time
from gspread_formatting import *
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)
app.secret_key = "admin"  # Change this to a secure key

# Google Sheets setup
SHEET_ID = '1-dHVAKHrsh9Xps1ZyAhB2XwDXSnx0QDZjJJAojfaCYY'  # Replace with your Google Sheet ID
CREDS_FILE = 'credentials.json'  # Path to your service account JSON file

# Initialize Google Sheets client
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, scope)
client = gspread.authorize(creds)

# Get the current month and year to create/use the appropriate sheet
now = datetime.now()
current_month_year = now.strftime("%Y-%m")  # Format: YYYY-MM

# Dummy credentials (You can store them in a database)
MANAGER_CREDENTIALS = {
    "username": "admin",
    "password": generate_password_hash("admin")  # Hashed password
}



# Dictionary with month numbers and Russian month names
months_of_year = {
    1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель", 5: "Май", 6: "Июнь",
    7: "Июль", 8: "Август", 9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
}


# Extract the current month number and year
current_month = int(now.strftime("%m"))  # Get month number (1 to 12)

# Get the Russian month name
current_month_name = months_of_year[current_month]

# Create the sheet name
SHEET_NAME = f"{current_month_name}"

days_in_month = {
    31: ['Январь', 'Март', 'Май', 'Июль', 'Август', 'Октябрь', 'Декабрь'],
    30: ['Апрель', 'Июнь', 'Сентябрь', 'Ноябрь'],
    28: ['Февраль']
}
def get_month_key(month_name):
    for key, value in days_in_month.items():
        if month_name in value:  # Check if month_name is in the list
            return key
    return None  

try:
    sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
except gspread.exceptions.WorksheetNotFound:
    # Create a new sheet for the month
    sheet = client.open_by_key(SHEET_ID).add_worksheet(title=SHEET_NAME, rows="100", cols="35")

    
    sheet.update_acell("R1","Красина")
    sheet.update_acell("A2",f"{current_month_name}")
    
    currnet_days_in_month = get_month_key(current_month_name)

    if currnet_days_in_month is not None:
        days_in_month_range = [str(i) for i in range(1, currnet_days_in_month + 1)]
    else:
        print(f"Error: Could not determine the number of days for {current_month_name}")
        days_in_month_range = []  # Empty if month is not found
    
    
    sheet.append_row(["Сотрудник"] + days_in_month_range)

    # Fetch employee names from database
    conn = sqlite3.connect('employees.db')
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM employee_faces')
    employees = cursor.fetchall()
    conn.close()

    # Add employees (each employee gets two rows)
    for employee in employees:
        name = employee[0]
        sheet.append_row([f"{name} (Start)"] + [""] * 31)
        sheet.append_row([f"{name} (End)"] + [""] * 31)

    print(f"✅ New sheet '{SHEET_NAME}' created with employees.")

def check_and_create_sheet_daily():
    global sheet  # Use the global sheet variable
    last_checked_month = None  # Track the last checked month

    while True:
        now = datetime.now()
        current_month_year = now.strftime("%Y-%m")  # Format: YYYY-MM

        
        # Extract the current month number and year
        current_month = int(now.strftime("%m"))  # Get month number (1 to 12)

        # Get the Russian month name
        current_month_name = months_of_year[current_month]

        if last_checked_month != current_month_year:
            last_checked_month = current_month_year  # Update the last checked month
            SHEET_NAME = f"{current_month_name}"  # Sheet name for the month

            try:
                sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
                print(f"✅ Sheet '{SHEET_NAME}' already exists.")
            except gspread.exceptions.WorksheetNotFound:
                # Create new sheet for the month
                sheet = client.open_by_key(SHEET_ID).add_worksheet(title=SHEET_NAME, rows="100", cols="35")
                sheet.update_acell("R1","Красина")
                sheet.update_acell("A2",f"{current_month_name}")

                currnet_days_in_month = get_month_key(current_month_name)

                if currnet_days_in_month is not None:
                    days_in_month_range = [str(i) for i in range(1, currnet_days_in_month + 1)]
                else:
                    print(f"Error: Could not determine the number of days for {current_month_name}")
                    days_in_month_range = []  # Empty if month is not found
    
                sheet.append_row(["Сотрудник"] + days_in_month_range)

                # Fetch employee names from database
                conn = sqlite3.connect('employees.db')
                cursor = conn.cursor()
                cursor.execute('SELECT name FROM employee_faces')
                employees = cursor.fetchall()
                conn.close()

                # Add employees (each employee gets two rows)
                for employee in employees:
                    name = employee[0]
                    sheet.append_row([f"{name} (Start)"] + [""] * 31)
                    sheet.append_row([f"{name} (End)"] + [""] * 31)

                print(f"✅ New sheet '{SHEET_NAME}' created with employees.")

        # Wait for 24 hours before checking again
        time.sleep(86400)

# Load known faces from the database
def load_known_faces():
    known_face_encodings = []
    known_face_names = []

    conn = sqlite3.connect('employees.db')
    cursor = conn.cursor()

    # Fetch all records from the database
    cursor.execute('SELECT name, face_encoding FROM employee_faces')
    records = cursor.fetchall()

    print(f"Loaded {len(records)} records from the database.")

    for record in records:
        name, face_encoding = record
        # Convert the face_encoding from bytes back to numpy array
        face_encoding = np.frombuffer(face_encoding, dtype=np.float64)
        print(f"Loaded face encoding for {name} with shape {face_encoding.shape}")
        known_face_encodings.append(face_encoding)
        known_face_names.append(name)

    conn.close()

    return known_face_encodings, known_face_names


# Global variables to store known faces
known_face_encodings, known_face_names = load_known_faces()


# Route to display the main page
@app.route('/')
def index():
    return render_template('index.html')


# Route to start attendance
@app.route('/start_attendance', methods=['GET'])
def start_attendance():
    return process_attendance("start")


# Route to end attendance
@app.route('/end_attendance', methods=['GET'])
def end_attendance():
    return process_attendance("end")


# Process attendance (start or end)
def process_attendance(shift_type):
    video_capture = cv2.VideoCapture(0)

    if not video_capture.isOpened():
        print("Unable to access the camera.")
        return jsonify({"status": "Error", "message": "Unable to access camera"})

    recorded_names = load_existing_attendance()
    frame_counter = 0
    process_every_n_frames = 5  # Process every 5th frame

    try:
        while True:
            ret, frame = video_capture.read()
            if not ret:
                print("Failed to read frame from camera.")
                break

            frame_counter += 1

            if frame_counter % process_every_n_frames == 0:
                small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
                rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

                face_locations = face_recognition.face_locations(rgb_small_frame)
                
                if not face_locations:
                    print("No face detected. Please position yourself in front of the camera.")
                    continue  # Don't exit the loop; keep checking for faces

                face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

                for face_encoding in face_encodings:
                    matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
                    face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
                    best_match_index = np.argmin(face_distances)

                    if matches[best_match_index]:
                        name = known_face_names[best_match_index]  # Ensure 'name' is assigned correctly

                        # Check if attendance is already recorded
                        start_recorded = f"{name} (Start)" in recorded_names
                        end_recorded = f"{name} (End)" in recorded_names

                        if (shift_type == "start" and start_recorded) or (shift_type == "end" and end_recorded):
                            print(f"{name} already recorded.")
                            return jsonify({"status": "AlreadyRecorded", "message": f"✅ {name} already recorded."})

                        current_time = datetime.now().strftime("%H:%M")  # Save only hours and minutes
                        save_attendance(name, current_time, shift_type)

                        print(f"✅ Attendance recorded for {name}.")
                        return jsonify({"status": "Success", "message": f"✅ Attendance recorded for {name}."})
                    
                    else:
                        print("Face detected, but no match found.")
                        return jsonify({"status": "NoMatch", "message": "Face detected but no match found."})

    finally:
        video_capture.release()

# Route to upload a new employee
@app.route('/upload', methods=['GET'])
def upload_form():
    if not session.get("manager_logged_in"):  # Check if manager is logged in
        return redirect(url_for("login"))  # Redirect to login if not authorized
    
    return render_template('upload.html')


# Route to handle employee upload
@app.route('/upload', methods=['POST'])
def upload_employee():
    if not session.get("manager_logged_in"):  # Check if manager is logged in
        return redirect(url_for("login"))  # Redirect to login if not authorized
    
    if 'file' not in request.files:
        return "No file uploaded", 400

    file = request.files['file']
    name = request.form.get('name')

    if file.filename == '' or not name:
        return "Invalid input", 400

    # Save the file temporarily
    file_path = f"temp_{file.filename}"
    file.save(file_path)

    # Compute face encoding
    image = face_recognition.load_image_file(file_path)
    face_encodings = face_recognition.face_encodings(image)

    if not face_encodings:
        return "No face detected in the image", 400

    face_encoding = face_encodings[0]
    face_encoding_bytes = face_encoding.tobytes()

    # Read the image as binary data
    with open(file_path, 'rb') as f:
        image_data = f.read()

    # Connect to the database
    conn = sqlite3.connect('employees.db')
    cursor = conn.cursor()

    # **Check if the name already exists**
    cursor.execute('SELECT name FROM employee_faces WHERE name = ?', (name,))
    existing_name = cursor.fetchone()
    if existing_name:
        conn.close()
        return f"Error: Employee with name '{name}' already exists!", 400

    # **Check if the face already exists**
    cursor.execute('SELECT face_encoding FROM employee_faces')
    all_encodings = cursor.fetchall()

    for record in all_encodings:
        stored_encoding = np.frombuffer(record[0], dtype=np.float64)
        match = face_recognition.compare_faces([stored_encoding], face_encoding)[0]

        if match:
            conn.close()
            return "Error: An employee with this face already exists!", 400

    # **If both checks pass, insert the new employee**
    cursor.execute('''
    INSERT INTO employee_faces (name, image, face_encoding)
    VALUES (?, ?, ?)
    ''', (name, image_data, face_encoding_bytes))

    conn.commit()
    conn.close()

    # Reload the known faces after uploading a new employee
    global known_face_encodings, known_face_names
    known_face_encodings, known_face_names = load_known_faces()

    print(f"Reloaded {len(known_face_encodings)} face encodings after uploading {name}.")


    # **Check if the employee already exists in the Google Sheet**
    sheet_data = sheet.get_all_records(head=3)
    existing_names = [record["Сотрудник"] for record in sheet_data if "Сотрудник" in record]

    if ((name +" (Start)") or (name +" (End)")) in existing_names:
        print(f"❌ Employee '{name}' is already in the Google Sheet. Skipping sheet update.")
    else:
        # Add new employee to Google Sheet (Start & End shift rows)
        sheet.append_row([f"{name} (Start)"] + [""] * 31)
        sheet.append_row([f"{name} (End)"] + [""] * 31)
        print(f"✅ Employee '{name}' added to the Google Sheet.")
    return redirect(url_for('upload_form'))  # Redirect back to the upload form


# Route to display all employees
@app.route('/employees')
def list_employees():
    if not session.get("manager_logged_in"):  # Check if manager is logged in
        return redirect(url_for("login"))  # Redirect to login if not authorized
    
    conn = sqlite3.connect('employees.db')
    cursor = conn.cursor()

    # Fetch all employee data
    cursor.execute('SELECT id, name, image FROM employee_faces')
    employees = cursor.fetchall()

    conn.close()

    # Convert image binary data to base64 for display in HTML
    employees_with_images = []
    for employee in employees:
        emp_id, name, image_data = employee
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        employees_with_images.append({
            'id': emp_id,
            'name': name,
            'image': image_base64
        })

    return render_template('employees.html', employees=employees_with_images)


# Route to delete an employee
@app.route('/delete_employee/<int:employee_id>', methods=['POST'])
def delete_employee(employee_id):
    conn = sqlite3.connect('employees.db')
    cursor = conn.cursor()

    # Delete the employee from the database
    cursor.execute('DELETE FROM employee_faces WHERE id = ?', (employee_id,))
    conn.commit()
    conn.close()

    # Reload the known faces after deletion
    global known_face_encodings, known_face_names
    known_face_encodings, known_face_names = load_known_faces()

    print(f"Reloaded {len(known_face_encodings)} face encodings after deletion.")

    return redirect(url_for('list_employees'))


# Load existing attendance data from Google Sheet with expected headers
def load_existing_attendance():
    expected_headers = ["Сотрудник"]  # List the expected headers
    records = sheet.get_all_records(head=3)
    return [record["Сотрудник"] for record in records]


# Save attendance under today's date
def save_attendance(name, time, shift_type):
    records = sheet.get_all_records(head=3)
    today_date = datetime.now().day  # Get today's date as an integer (1-31)

    # Determine row label based on shift type
    row_label = f"{name} (Start)" if shift_type == "start" else f"{name} (End)"

    row_index = None
    for i, record in enumerate(records):
        if record["Сотрудник"] == row_label:
            row_index = i + 4  # Adjusting for header row
            break

    col_index = today_date + 1  # Shift right (1st column is "Сотрудник", so day 1 is at index 2)

    if row_index:
        existing_value = sheet.cell(row_index, col_index).value  # Get current value
        if existing_value:
            print(f"⚠️ Attendance already recorded for {name} on {today_date}. Skipping update.")
            return {"status": "AlreadyRecorded", "message": f"{name} already recorded for today."}
            
        else:
            sheet.update_cell(row_index, col_index, time)  # Update attendance for today
            return {"status": "Success", "message": f"Attendance recorded for {name}."}
    else:
        # If employee is missing, add them with two rows
        sheet.append_row([f"{name} (Start)"] + [""] * 31)
        sheet.append_row([f"{name} (End)"] + [""] * 31)
        new_row_index = len(records) + 2 if shift_type == "start" else len(records) + 3
        sheet.update_cell(new_row_index, col_index, time)
        return {"status": "Success", "message": f"Attendance recorded for {name}."}

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == MANAGER_CREDENTIALS["username"] and check_password_hash(MANAGER_CREDENTIALS["password"], password):
            session["manager_logged_in"] = True  # Store login session
            return redirect(url_for("list_employees"))

        return "Invalid username or password", 403  # Unauthorized access

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("manager_logged_in", None)  # Remove login session
    return redirect(url_for("index"))

# Run the Flask app
if __name__ == "__main__":
    threading.Thread(target=check_and_create_sheet_daily, daemon=True).start()
    app.run(debug=True)