import os
from tensorflow.keras.models import load_model

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    face_model = load_model(os.path.join(BASE_DIR, "Models/face_emotion_model.h5"))
    print("Face model input shape:", face_model.input_shape)
except Exception as e:
    print("Face model error:", e)

try:
    voice_model = load_model(os.path.join(BASE_DIR, "Models/SER_Interview_Model_v1 (1).keras"))
    print("Voice model input shape:", voice_model.input_shape)
except Exception as e:
    print("Voice model error:", e)
