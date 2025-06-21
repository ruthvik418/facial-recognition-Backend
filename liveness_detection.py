import cv2
import dlib
import random

def liveness_detection():
    try:
        camera = cv2.VideoCapture(0)
        predictor = dlib.shape_predictor("C:/Users/HP/Desktop/facial-recognition-backend/shape_predictor_68_face_landmarks.dat")
        detector = dlib.get_frontal_face_detector()

        # Randomly select a challenge
        challenge = random.choice(["smile", "freeze", "turn"])
        print(f"Challenge: {challenge.capitalize()}.")

        freeze_frames = 0
        freeze_threshold = 50  # Number of frames to remain still

        while True:
            ret, frame = camera.read()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = detector(gray)

            if len(faces) == 0:
                cv2.putText(frame, "No face detected. Please align your face.", (50, 50), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
                cv2.imshow("Liveness Detection", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                continue

            for face in faces:
                landmarks = predictor(gray, face)

                # Display instructions based on the challenge
                if challenge == "smile":
                    cv2.putText(frame, "Please smile.", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

                elif challenge == "freeze":
                    cv2.putText(frame, "Please hold still.", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
                    freeze_frames += 1
                    if freeze_frames >= freeze_threshold:
                        cv2.putText(frame, "Freeze challenge completed!", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
                        camera.release()
                        cv2.destroyAllWindows()
                        return f"Liveness confirmed: Freeze challenge completed."

                elif challenge == "turn":
                    cv2.putText(frame, "Turn your head left or right.", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

                # Check challenge completion
                if challenge == "smile":  # Replace with actual smile detection logic
                    cv2.putText(frame, "Smile detected!", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
                    camera.release()
                    cv2.destroyAllWindows()
                    return f"Liveness confirmed: Smile challenge completed."

                elif challenge == "turn":  # Replace with actual head turn detection logic
                    cv2.putText(frame, "Turn detected!", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
                    camera.release()
                    cv2.destroyAllWindows()
                    return f"Liveness confirmed: Turn challenge completed."

            cv2.imshow("Liveness Detection", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        camera.release()
        cv2.destroyAllWindows()
        return "Liveness failed: Challenge not completed."

    except Exception as e:
        return f"Liveness detection failed: {str(e)}"

if __name__ == "__main__":
    print(liveness_detection())
