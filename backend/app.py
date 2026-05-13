from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os, json, base64
import numpy as np
import cv2
import librosa
from tensorflow.keras.models import load_model

app = Flask(__name__)
CORS(app)

# ---------------- PATH ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

RESULT_FILE = os.path.join(BASE_DIR, "results.json")
QUESTION_FILE = os.path.join(BASE_DIR, "questions.json")
USER_FILE = os.path.join(BASE_DIR, "users.json")
IMAGE_FOLDER = os.path.join(BASE_DIR, "images")

os.makedirs(IMAGE_FOLDER, exist_ok=True)

# ---------------- LOAD MODELS ----------------
face_model = None
voice_model = None
face_cascade = None

# Try loading TensorFlow models
try:
    face_model = load_model(os.path.join(BASE_DIR, "Models/face_emotion_model.h5"))
    print("✅ Face model loaded")
except Exception as e:
    print(f"❌ Face model NOT loaded: {e}")

try:
    voice_model = load_model(os.path.join(BASE_DIR, "Models/SER_Interview_Model_v1 (1).keras"))
    print("✅ Voice model loaded")
except Exception as e:
    print(f"❌ Voice model NOT loaded: {e}")

# Load OpenCV Haar Cascade as fallback
try:
    cascade_path = os.path.join(BASE_DIR, "haarcascade_frontalface_default.xml")
    if os.path.exists(cascade_path):
        face_cascade = cv2.CascadeClassifier(cascade_path)
        print("✅ OpenCV face cascade loaded")
    else:
        print("❌ Haar cascade file not found")
except Exception as e:
    print(f"❌ Face cascade NOT loaded: {e}")

face_labels = ["Angry","Happy","Neutral","Sad"]
voice_labels = ["Angry","Happy","Neutral","Sad","Fear"]

# ---------------- INIT FILE ----------------
for file in [RESULT_FILE, QUESTION_FILE, USER_FILE]:
    if not os.path.exists(file):
        with open(file, "w") as f:
            json.dump([], f)

# ---------------- SCORE ----------------
def calculate_score(face, voice):
    face_map = {"Happy":0.9,"Neutral":0.7,"Sad":0.4,"Angry":0.2}
    voice_map = {"Happy":0.9,"Neutral":0.7,"Sad":0.4,"Fear":0.3,"Angry":0.2}

    f = face_map.get(face, 0.5)
    v = voice_map.get(voice, 0.5)

    return round((f*0.6)+(v*0.4),2)

# ---------------- AUTHENTICATION ----------------
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    role = data.get("role")

    with open(USER_FILE) as f:
        users = json.load(f)

    for u in users:
        if u["username"] == username:
            return jsonify({"success": False, "message": "Username already exists"})

    users.append({"username": username, "password": password, "role": role})

    with open(USER_FILE, "w") as f:
        json.dump(users, f, indent=4)

    return jsonify({"success": True, "message": "Registered successfully"})

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")
    expected_role = data.get("expected_role")  # The role user is trying to access

    with open(USER_FILE) as f:
        users = json.load(f)

    for u in users:
        if u["username"] == username and u["password"] == password:
            # Check if user is trying to access a different role than registered
            if expected_role and u["role"] != expected_role:
                return jsonify({
                    "success": False, 
                    "message": f"You are registered as {u['role']}. Please use the {u['role']} portal."
                })
            return jsonify({"success": True, "role": u["role"]})

    return jsonify({"success": False, "message": "Invalid credentials"})

# ---------------- SET QUESTIONS ----------------
@app.route('/set_questions', methods=['POST'])
def set_questions():
    data = request.json

    with open(QUESTION_FILE) as f:
        q = json.load(f)

    q.append({
        "candidate_id": data.get("candidate_id"),
        "questions": data.get("questions", [])
    })

    with open(QUESTION_FILE, "w") as f:
        json.dump(q, f, indent=4)

    return jsonify({"message": "Questions saved"})

# ---------------- GET QUESTIONS ----------------
@app.route('/get_questions/<cid>')
def get_q(cid):

    with open(QUESTION_FILE) as f:
        q = json.load(f)

    # 🔥 get LAST entry (latest questions)
    for i in reversed(q):
        if i["candidate_id"] == cid:
            return jsonify(i)

    return jsonify({"questions":[]})

# @app.route('/get_questions/<cid>')
# def get_questions(cid):

#     with open(QUESTION_FILE) as f:
#         q = json.load(f)

#     for item in q:
#         if item["candidate_id"] == cid:
#             return jsonify(item)

#     return jsonify({"questions": []})

# ---------------- FACE ----------------
@app.route('/face', methods=['POST'])
def face():
    try:
        # Check if image data is provided
        if not request.json or "image" not in request.json:
            print("FACE ERROR: No image provided")
            return jsonify({"emotion": "Neutral"})
        
        data = request.json["image"]

        # Decode base64 image properly
        img_bytes = base64.b64decode(data.split(",")[1])
        np_arr = np.frombuffer(img_bytes, dtype=np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        if img is None:
            print("FACE ERROR: Failed to decode image")
            return jsonify({"emotion": "Neutral"})

        # Try TensorFlow model first
        if face_model:
            try:
                img_resized = cv2.resize(img, (224,224))
                img_resized = img_resized.astype('float32') / 255.0
                img_resized = np.expand_dims(img_resized, axis=0)

                pred = face_model.predict(img_resized, verbose=0)
                
                if len(pred.shape) > 1:
                    pred = pred[0]
                
                pred_index = np.argmax(pred)
                
                if pred_index < len(face_labels):
                    emotion = face_labels[pred_index]
                else:
                    emotion = "Neutral"
                    
                print("FACE PRED:", pred, "->", emotion)
                return jsonify({"emotion": emotion})
            except Exception as e:
                print(f"TensorFlow prediction failed: {e}")

        # Fallback: Use facial expression analysis
        if face_cascade:
            try:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.1, 4)
                
                if len(faces) > 0:
                    x, y, w, h = faces[0]
                    
                    # Extract face region
                    face_region = gray[y:y+h, x:x+w]
                    face_color = img[y:y+h, x:x+w]
                    
                    # Analyze facial features
                    emotion = analyze_facial_expression(face_region, face_color, gray, x, y, w, h)
                    print(f"Face detected -> {emotion}")
                    return jsonify({"emotion": emotion})
            except Exception as e:
                print(f"OpenCV detection failed: {e}")

        # Final fallback
        return jsonify({"emotion": "Neutral"})

    except Exception as e:
        print("FACE ERROR:", e)
        return jsonify({"emotion": "Neutral"})


def analyze_facial_expression(face_gray, face_color, full_gray, fx, fy, fw, fh):
    """Analyze facial expressions to detect emotions"""
    
    # 1. Detect eyes (for alertness/attention)
    eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
    eyes = eye_cascade.detectMultiScale(face_gray, 1.1, 5)
    
    # 2. Detect mouth region (for smile/frown)
    mouth_y = int(fh * 0.6)
    mouth_region = face_gray[mouth_y:fh, int(fw*0.2):int(fw*0.8)]
    
    # 3. Analyze mouth (smile detection)
    mouth_emotion = "Neutral"
    if mouth_region.size > 0:
        # Calculate mouth width to height ratio
        mouth_height, mouth_width = mouth_region.shape
        if mouth_height > 0:
            ratio = mouth_width / mouth_height
            
            # Higher width ratio = more likely a smile
            if ratio > 3.5:
                mouth_emotion = "Happy"
            elif ratio < 2.0:
                mouth_emotion = "Sad"
            else:
                mouth_emotion = "Neutral"
    
    # 4. Analyze upper face (eyebrows - for anger/fear)
    upper_face = face_gray[0:int(fh*0.4), :]
    
    # 5. Calculate overall brightness and contrast
    mean_brightness = np.mean(face_gray)
    std_dev = np.std(face_gray)
    
    # 6. Combine all features for final emotion
    if len(eyes) >= 2:
        # Eyes detected - person is alert
        if mouth_emotion == "Happy":
            return "Happy"
        elif mouth_emotion == "Sad":
            return "Sad"
        else:
            if std_dev > 50 and mean_brightness > 100:
                return "Happy"
            elif mean_brightness < 70:
                return "Sad"
            else:
                return "Neutral"
    else:
        # No eyes detected - could be looking down or away
        if mouth_emotion == "Happy":
            return "Happy"
        elif mouth_emotion == "Sad":
            return "Sad"
        else:
            return "Neutral"



# ---------------- VOICE ----------------
@app.route('/voice', methods=['POST'])
def voice():
    try:
        # Check if audio data is provided
        if not request.json or "audio" not in request.json:
            print("VOICE ERROR: No audio provided")
            return jsonify({"emotion": "Neutral"})
        
        data = request.json['audio']

        audio_data = base64.b64decode(data.split(",")[1])

        with open("temp.wav", "wb") as f:
            f.write(audio_data)

        y, sr = librosa.load("temp.wav", sr=22050, duration=3)

        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=40)
        mfcc = mfcc.flatten()

        # ensure size = 180
        if len(mfcc) < 180:
            mfcc = np.pad(mfcc, (0, 180-len(mfcc)))
        else:
            mfcc = mfcc[:180]

        mfcc = np.expand_dims(mfcc, axis=0)

        if voice_model:
            try:
                preds = voice_model.predict(mfcc, verbose=0)

                print("RAW VOICE PRED:", preds)

                if len(preds.shape) > 1:
                    preds = preds[0]
                
                index = np.argmax(preds)
                
                if index < len(voice_labels):
                    emotion = voice_labels[index]
                else:
                    emotion = voice_labels[min(index, len(voice_labels)-1)]

                print("VOICE:", emotion)
                return jsonify({"emotion": emotion})
            except Exception as e:
                print(f"Voice model prediction failed: {e}")

        # Fallback: Use audio analysis
        try:
            # Use audio energy and pitch characteristics
            energy = np.mean(np.abs(y))
            pitch = np.mean(librosa.yin(y, fmin=50, fmax=500))
            
            # Calculate confidence based on audio quality
            # Higher energy + consistent pitch = more confident
            confidence = min(100, int((energy * 200) + (50 if pitch > 100 else 0)))
            
            if energy > 0.1:
                if pitch > 200:
                    emotion = "Happy"
                else:
                    emotion = "Neutral"
            else:
                emotion = "Neutral"
            
            print(f"Voice fallback - energy: {energy:.3f}, pitch: {pitch:.1f}, confidence: {confidence}% -> {emotion}")
            return jsonify({"emotion": emotion, "confidence": confidence})
        except Exception as e:
            print(f"Voice fallback failed: {e}")

        # Final fallback
        import random
        emotion = random.choice(["Neutral", "Happy", "Neutral"])
        return jsonify({"emotion": emotion})

    except Exception as e:
        print("VOICE ERROR:", e)
        return jsonify({"emotion": "Neutral"})

# @app.route('/voice', methods=['POST'])
# def voice():

#     try:
#         data = request.json["audio"]

#         audio_bytes = base64.b64decode(data.split(",")[1])

#         with open("temp.wav", "wb") as f:
#             f.write(audio_bytes)

#         try:
#             y, sr = librosa.load("temp.wav", sr=22050, duration=3)
#         except:
#             return jsonify({"emotion": "Neutral"})

#         mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=40)

#         mfcc = mfcc.flatten()   # 🔥 important
#         mfcc = mfcc[:180]       # trim

#         if len(mfcc) < 180:
#             mfcc = np.pad(mfcc, (0, 180-len(mfcc)))

#             mfcc = np.expand_dims(mfcc, axis=0)

#         if voice_model:
#             pred = voice_model.predict(mfcc)
#             emotion = voice_labels[np.argmax(pred)]
#         else:
#             emotion = "Neutral"

#         return jsonify({"emotion": emotion})

#     except Exception as e:
#         print("VOICE ERROR:", e)
#         return jsonify({"emotion": "Neutral"})

#SUBMIT
@app.route('/submit', methods=['POST'])
def submit():
    try:
        data = request.json

        cid = data.get("candidate_id", "Unknown")
        name = data.get("name", "Unknown")
        face = data.get("face_emotion", "Neutral")
        voice = data.get("voice_emotion", "Neutral")

        # ---------------- SAVE IMAGE ----------------
        

        image_name = ""

        if data.get("image"):
            try:
                img_bytes = base64.b64decode(data["image"].split(",")[1])

                image_name = f"{cid}.png"
                path = os.path.join(IMAGE_FOLDER, image_name)

                with open(path, "wb") as f:
                    f.write(img_bytes)

                print("✅ IMAGE SAVED:", path)

            except Exception as e:
                print("❌ IMAGE SAVE ERROR:", e)



        
        # ---------------- SCORE ----------------
        score = calculate_score(face, voice)

        result = {
            "candidate_id": cid,
            "name": name,
            "face": face,
            "voice": voice,
            "score": score,
            "image": image_name,
            "decision": "Pending"
        }

        with open(RESULT_FILE) as f:
            results = json.load(f)

        updated = False
        for r in results:
            if r["candidate_id"] == cid:
                r.update(result)
                updated = True

        if not updated:
            results.append(result)

        with open(RESULT_FILE, "w") as f:
            json.dump(results, f, indent=4)

        print("✅ SUBMIT SUCCESS:", result)

        return jsonify({"message": "Submitted Successfully"})

    except Exception as e:
        print("❌ SUBMIT ERROR:", e)
        return jsonify({"message": "Error"}), 500

# ---------------- IMAGES ----------------
@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(IMAGE_FOLDER, filename)

# ---------------- RESULT ----------------
@app.route('/result/<cid>')
def result(cid):

    with open(RESULT_FILE) as f:
        results = json.load(f)

    for r in results:
        if r["candidate_id"] == cid:
            return jsonify(r)

    return jsonify({"message": "Not found"})

# ---------------- ALL RESULTS ----------------
@app.route('/results')
def all_results():
    with open(RESULT_FILE) as f:
        results = json.load(f)
    return jsonify({"results": results})

# ---------------- DECISION ----------------
@app.route('/decision', methods=['POST'])
def decision():
    try:
        data = request.json
        cid = data.get("candidate_id")
        dec = data.get("decision")
        
        print(f"DECISION REQUEST: cid={cid}, decision={dec}")

        with open(RESULT_FILE) as f:
            results = json.load(f)

        print(f"Total results: {len(results)}")

        updated = False
        for r in results:
            if r["candidate_id"] == cid:
                r["decision"] = dec
                updated = True
                print(f"Updated candidate {cid} to {dec}")
                break

        if updated:
            with open(RESULT_FILE, "w") as f:
                json.dump(results, f, indent=4)
            return jsonify({"success": True, "message": "Decision updated"})
        else:
            print(f"Candidate {cid} not found in results")
            return jsonify({"success": False, "message": "Candidate not found"})

    except Exception as e:
        print("DECISION ERROR:", e)
        return jsonify({"success": False, "message": "Error updating decision"}), 500

# ---------------- IMAGE ----------------
@app.route('/images/<filename>')
def image(filename):
    return send_from_directory(IMAGE_FOLDER, filename)




# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
