import cv2
import numpy as np
import os
import requests

class FaceRecognitionModule:
    """
    Production-grade Face Recognition using OpenCV's DNN FaceRecognizerSF (SFace)
    and FaceDetectorYN (YuNet). No dlib required.
    Compatible with Windows Python 3.13.
    """
    def __init__(self, dataset_path="datasets/faces/", model_dir="models/"):
        self.dataset_path = dataset_path
        self.model_dir = model_dir
        
        # URLs for models
        self.detector_url = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
        self.recognizer_url = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"
        
        self.detector_path = os.path.join(model_dir, "face_detection_yunet.onnx")
        self.recognizer_path = os.path.join(model_dir, "face_recognition_sface.onnx")
        
        self.ensure_models_exist()
        
        # Initialize OpenCV DNN models
        self.detector = cv2.FaceDetectorYN.create(
            self.detector_path, "", (320, 320), score_threshold=0.6, nms_threshold=0.3, top_k=5000
        )
        self.recognizer = cv2.FaceRecognizerSF.create(self.recognizer_path, "")
        
        self.known_face_features = [] # List of (student_id, feature_vector)
        self.load_known_faces()

    def _extract_student_id(self, root: str, filename: str) -> str:
        """
        Normalize any dataset layout into a roll-number-like identifier.

        Supported layouts:
        - datasets/faces/ROLL001.jpg
        - datasets/faces/ROLL001_0.jpg
        - datasets/faces/ROLL001_Name/ROLL001_0.jpg
        - datasets/faces/ROLL001_Name/anything.jpg
        """
        # If images are inside a per-student folder, prefer the folder name.
        base_dir = os.path.basename(root.rstrip("/\\"))
        if base_dir and base_dir.lower() != os.path.basename(self.dataset_path.rstrip("/\\")).lower():
            # Folder is typically "ROLL001_Name" or "ROLL001"
            return base_dir.split("_")[0]

        # Otherwise, derive from the filename.
        stem = os.path.splitext(filename)[0]
        return stem.split("_")[0]

    def ensure_models_exist(self):
        if not os.path.exists(self.model_dir):
            os.makedirs(self.model_dir)
            
        for path, url in [(self.detector_path, self.detector_url), (self.recognizer_path, self.recognizer_url)]:
            if not os.path.exists(path):
                print(f"Downloading model from {url}...")
                response = requests.get(url)
                with open(path, "wb") as f:
                    f.write(response.content)
                print(f"Model saved to {path}")

    def load_known_faces(self):
        print("Training AI Face Encodings...")
        self.known_face_features = [] # Clear existing to allow re-training
        
        # 1. Load existing embeddings from database first (super fast)
        cached_rolls = set()
        try:
            from database.student_queries import get_all_embeddings
            rows = get_all_embeddings()
            if rows:
                for roll_number, embedding_bytes in rows:
                    feature = np.frombuffer(embedding_bytes, dtype=np.float32).reshape(1, 128)
                    self.known_face_features.append((roll_number, feature))
                    cached_rolls.add(roll_number)
                print(f"AI Trained from Database Cache: {len(self.known_face_features)} face signatures loaded.")
        except Exception as e:
            print(f"[AI] Error loading embeddings from database: {e}")

        # 2. Check for any missing student faces in datasets/faces/ that are not cached yet
        new_cached_count = 0
        for root, dirs, files in os.walk(self.dataset_path):
            for filename in files:
                if filename.lower().endswith((".jpg", ".png", ".jpeg")):
                    student_id = self._extract_student_id(root, filename)
                    # Map folder prefixes to real database roll numbers for cache checking & training
                    if student_id == '0026' or student_id == '26':
                        student_id = '11523050029'
                    elif student_id == '0541' or student_id == '541':
                        student_id = '11523050541'
                    # If this student's embedding is already loaded, skip processing their file!
                    if student_id in cached_rolls:
                        continue
                    
                    img_path = os.path.join(root, filename)
                    image = cv2.imread(img_path)
                    if image is None: continue
                    
                    # Detect and extract features
                    height, width, _ = image.shape
                    self.detector.setInputSize((width, height))
                    _, faces = self.detector.detect(image)
                    
                    if faces is not None:
                        # Align and extract
                        aligned_face = self.recognizer.alignCrop(image, faces[0])
                        feature = self.recognizer.feature(aligned_face)
                        self.known_face_features.append((student_id, feature))
                        cached_rolls.add(student_id)
                        new_cached_count += 1
                        
                        # Cache in database for next runs
                        try:
                            from database.student_queries import get_student_by_roll, save_student_embedding
                            student = get_student_by_roll(student_id)
                            if student:
                                save_student_embedding(student[0], feature.tobytes())
                        except Exception as ex:
                            pass
                            
        if new_cached_count > 0:
            print(f"AI scanned filesystem and cached {new_cached_count} new signatures in database.")
        print(f"AI Training complete. Total face signatures: {len(self.known_face_features)}")

    def recognize_face(self, frame, bbox_ltrb):
        """
        Takes a frame and a bounding box, returns student_id or 'Unknown'
        """
        # Crop the face for detection within/around the box
        l, t, r, b = [int(x) for x in bbox_ltrb]
        # Expand slightly
        pad = 20
        face_img = frame[max(0, t-pad):min(frame.shape[0], b+pad), max(0, l-pad):min(frame.shape[1], r+pad)]
        
        if face_img.size == 0: return "Unknown"
        
        # Detect face in the crop
        h, w, _ = face_img.shape
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(face_img)
        
        if faces is None: return "Unknown"
        
        # Extract features from the first face found in crop
        aligned_face = self.recognizer.alignCrop(face_img, faces[0])
        query_feature = self.recognizer.feature(aligned_face)
        
        # Compare with known features
        best_match = "Unknown"
        max_score = 0.0
        
        for student_id, known_feature in self.known_face_features:
            score = self.recognizer.match(query_feature, known_feature, cv2.FaceRecognizerSF_FR_COSINE)
            if score > max_score:
                max_score = score
                best_match = student_id
                
        if max_score > 0.30: # Use slightly more tolerant threshold for demonstration
            return best_match
            
        return "Unknown"

    def validate_image(self, img_path):
        """
        Validates if a photo has exactly one clear face.
        Returns (is_valid, message)
        """
        image = cv2.imread(img_path)
        if image is None: return False, "Could not open Image."
        
        h, w, _ = image.shape
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(image)
        
        if faces is None:
            return False, "No face detected. Please ensure your photo is clear and your face is fully visible."
        
        if len(faces) > 1:
            return False, "Multiple faces detected. Please upload photos with only ONE person."
            
        # YuNet score is at faces[0][-1]
        score = faces[0][-1]
        if score < 0.75: # Lowered to 0.75 to allow side angles which are naturally lower score
            return False, "Photo is too blurry or face not clear enough. Please upload a high-quality picture."
            
        return True, "OK"
