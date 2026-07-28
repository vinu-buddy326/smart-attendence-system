from ultralytics import YOLO
import cv2

class PersonDetector:
    def __init__(self, model_path="yolov8n.pt"):
        self.model = YOLO(model_path)

    def detect_persons(self, frame):
        # class 0 in COCO is person
        results = self.model.predict(frame, classes=[0], conf=0.5, verbose=False)
        detections = []
        for r in results:
            for box in r.boxes:
                # [x1, y1, x2, y2, confidence, class]
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = box.conf[0].item()
                detections.append(([int(x1), int(y1), int(x2-x1), int(y2-y1)], conf, 'person'))
        return detections

if __name__ == "__main__":
    detector = PersonDetector()
    cap = cv2.VideoCapture(0)
    while True:
        ret, frame = cap.read()
        if not ret: break
        dets = detector.detect_persons(frame)
        for (bbox, conf, cls) in dets:
            x, y, w, h = bbox
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
        cv2.imshow("Detection Test", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'): break
    cap.release()
    cv2.destroyAllWindows()
