import cv2
import numpy as np
import os

class BodyRecognitionFallback:
    def __init__(self, body_dataset_path="datasets/bodies/"):
        self.body_dataset_path = body_dataset_path
        self.student_hists = [] # List of (student_id, histogram)
        self.load_bodies()

    def load_bodies(self):
        for filename in os.listdir(self.body_dataset_path):
            if filename.lower().endswith((".jpg", ".png", ".jpeg")):
                img = cv2.imread(os.path.join(self.body_dataset_path, filename))
                if img is not None:
                    hist = self.get_histogram(img)
                    self.student_hists.append((filename.split('.')[0], hist))

    def get_histogram(self, img):
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [180, 256], [0, 180, 0, 256])
        cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
        return hist

    def recognize_body(self, person_crop):
        if person_crop.size == 0: return None
        curr_hist = self.get_histogram(person_crop)
        best_score = 0
        best_name = None
        for name, hist in self.student_hists:
            # Correlation comparison
            score = cv2.compareHist(curr_hist, hist, cv2.HISTCMP_CORREL)
            if score > best_score and score > 0.8: # Threshold 0.8
                best_score = score
                best_name = name
        return best_name
