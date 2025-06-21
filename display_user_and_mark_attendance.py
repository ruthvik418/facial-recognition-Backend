import cv2
import dlib
from mark_attendance import get_user_info, mark_attendance

def display_id_and_mark_attendance():
    try:
        camera = cv2.VideoCapture(0)
        predictor = dlib.shape_predictor("C:/Users/HP/Desktop/facial-recognition-backend/shape_predictor_68_face_landmarks.dat")
        detector = dlib.get_frontal_face_detector()

        # Simulate recognized user ID (Replace with facial recognition logic)
        user_id = "23241A0542"  # Example recognized user ID
        user_name = get_user_info(user_id)  # Fetch user name from DynamoDB

        if user_name != "Unknown User":
            mark_attendance(user_id)  # Log attendance

        while True:
            ret, frame = camera.read()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = detector(gray)

            if len(faces) == 0:
                cv2.putText(frame, "No face detected. Please align your face.", (50, 50), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
                cv2.imshow("Attendance System", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                continue

            for face in faces:
                landmarks = predictor(gray, face)

                # Detect forehead region using facial landmarks
                forehead_x = landmarks.part(21).x
                forehead_y = landmarks.part(21).y - 30

                # Display the user's ID and name on their forehead
                cv2.putText(frame, f"{user_name} ({user_id})", (forehead_x - 50, forehead_y),
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

            cv2.imshow("Attendance System", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        camera.release()
        cv2.destroyAllWindows()

    except Exception as e:
        print(f"Error occurred: {str(e)}")

if __name__ == "__main__":
    display_id_and_mark_attendance()
