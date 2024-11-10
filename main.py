import cv2
import face_recognition
import numpy as np
import csv
import os
from datetime import datetime
from flask import Flask, render_template, jsonify

app = Flask(__name__)

photos_folder = 'photos/'
now = datetime.now()
current_date = now.strftime("%Y-%m-%d")


def ensure_attendance_file():
    """Ensure the CSV file for today's attendance exists."""
    if not os.path.exists(current_date + '.csv'):
        with open(current_date + '.csv', 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Employee", "Arrive Time"])  # Write header row
        print(f"Created new attendance file: {current_date}.csv")


def load_known_faces():
    known_face_encodings = []
    known_face_names = []

    for filename in os.listdir(photos_folder):
        if filename.endswith((".png", ".jpg", ".jpeg")):
            image_path = os.path.join(photos_folder, filename)
            image = face_recognition.load_image_file(image_path)
            face_encoding = face_recognition.face_encodings(image)

            if face_encoding:
                known_face_encodings.append(face_encoding[0])
                name = os.path.splitext(filename)[0]  # Use filename as person's name
                known_face_names.append(name)

    return known_face_encodings, known_face_names


known_face_encodings, known_face_names = load_known_faces()

# Ensure the attendance file is created on startup
ensure_attendance_file()


def load_existing_attendance():
    """Load existing attendance data from CSV"""
    if os.path.exists(current_date + '.csv'):
        with open(current_date + '.csv', 'r') as f:
            csv_reader = csv.reader(f)
            next(csv_reader, None)  # Skip header
            return [row[0] for row in csv_reader if row]
    return []


def save_attendance(name, time):
    """Save attendance to CSV"""
    with open(current_date + '.csv', 'a', newline='') as f:
        lnwriter = csv.writer(f)
        lnwriter.writerow([name, time])


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/start_attendance', methods=['GET'])
def start_attendance():
    video_capture = cv2.VideoCapture(0)

    if not video_capture.isOpened():
        print("Unable to access the camera.")
        return jsonify({"status": "Error", "message": "Unable to access camera"})

    recorded_names = load_existing_attendance()
    frame_counter = 0
    attendance_status = {"status": "NoFaceDetected"}

    process_every_n_frames = 10  # Process every 10th frame

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
                print(f"Detected {len(face_locations)} face(s) in the frame.")

                face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

                for face_encoding in face_encodings:
                    matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
                    face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)
                    best_match_index = np.argmin(face_distances)

                    print(f"Matches: {matches}")

                    if matches[best_match_index]:
                        name = known_face_names[best_match_index]

                        if name in recorded_names:
                            attendance_status = {"status": "AlreadyRecorded", "name": name}
                            print(f"{name} already recorded.")
                            break  # Break out of the face processing loop to return status.

                        recorded_names.append(name)
                        current_time = datetime.now().strftime("%H:%M:%S")
                        save_attendance(name, current_time)

                        attendance_status = {"status": "Success", "name": name}
                        print(f"Attendance recorded for {name}.")
                        break  # Break out to return status.

                if attendance_status["status"] in ["Success", "AlreadyRecorded"]:
                    break  # Exit the main loop to return the status.

    finally:
        video_capture.release()

    print(f"Final attendance status: {attendance_status}")
    return jsonify(attendance_status)


if __name__ == "__main__":
    app.run(debug=True)
