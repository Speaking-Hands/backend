from utils.functions import *
from model import *
import os
import uuid
import cv2
import json
import tempfile
import mediapipe as mp
import tensorflow as tf
from functools import wraps
from flask_cors import CORS, cross_origin
from flask import Flask, request, make_response
from datetime import timedelta
from google.cloud import storage
from google.auth import default
from google.auth import transport
from pathlib import Path


app = Flask(__name__)


#------ API SECURITY -------
app.config['CORS_HEADERS'] = 'Content-Type'
os.environ["API_KEY"] = "PwBpyZ0rW57yrbcNUhFUNaVJMMWDbwm6"

cors = CORS(app)

def login_required(f):
    @wraps(f)
    def token_check(*args, **kwargs):
        # Token Exists
        if "x-api-key" not in request.headers:
            return make_response({"error": "Authentication Failed: You need an API Key"}, 400)
        # Token Validation
        if request.headers["x-api-key"] != os.environ["API_KEY"]:
            return make_response({"error": "Authentication Failed: Invalid API Key"}, 400)
        # Execute endpoint function
        return f(*args, **kwargs)
    return token_check


#------ API REST -------
@app.route("/")
@cross_origin()
@login_required
def main():
    """
    Testing API endpoint
    """
    return make_response("SpeakingHands API working fine! :)", 200)


@app.route("/parquet", methods=["POST"])
@cross_origin()
@login_required
def parquet():
    """
    Upload video and transform it into parquet
    """   
    # Comprobamos video
    if 'video' not in request.files or request.files['video'].filename == '':
        return make_response({"error": "You must send a video with the next tag: 'video'"}, 400)
    
    video = request.files["video"]

    if video.content_type.split("/")[0] != "video":
        return make_response({"error": "File uploaded is not a video"}, 400)
    
    with tempfile.TemporaryDirectory() as td:

        # Guardamos video temporalmente
        temp_filename = Path(td) / 'uploaded_video'
        request.files['video'].save(temp_filename)

        # Transformamos a parquet
        mp_holistic = mp.solutions.holistic
        cap = cv2.VideoCapture(str(temp_filename))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        parquet_row_list = []
        parquet_id = uuid.uuid4().hex

        with mp_holistic.Holistic( static_image_mode=False, model_complexity=1) as holistic:
            print(f"Procesando '{parquet_id}'. Número de frames a procesar: {total_frames}")
            for frame_num in range(total_frames):
                # Procesamos frame
                ret, frame = cap.read()
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = holistic.process(frame_rgb)
                frame_row_result = create_frame_row(frame_num, results)
                parquet_row_list.append(frame_row_result)

            parquet = pd.concat(parquet_row_list, axis=0)

            # Guardamos en GCP
            print(f"'{parquet_id}' procesado correctamente! Guardando parquet")
            client = storage.Client()
            bucket = client.get_bucket('speakinghands_cloudbuild')
            bucket.blob(f'parquets/{parquet_id}.parquet').upload_from_string(parquet.to_parquet())

        cap.release() 

    result = {
        "parquet": parquet_id
    }

    return make_response(result, 200)

@app.route("/predict", methods=["POST"])
@cross_origin()
@login_required
def translate():
    """
    Translate selected parquet
    """      
    # Comprobamos entrada
    if "parquet" not in list(request.form.keys()):
        return make_response({"error": "Invalid request params. Expected only 'parquet' entry"}, 400)

    if (len(list(request.form.keys())) + len(list(request.files.keys()))) > 1:
        return make_response({"error": "You can't send more than 1 request param. Expected only 'parquet' entry"}, 400)

    # Leer el archivo 'inference_args.json' para obtener las columnas seleccionadas
    with open(str(os.path.abspath("model/inference_args.json")), 'r') as f:
        inference_args = json.load(f)
    selected_columns = inference_args['selected_columns']
    
    # Frames video (parquet GCP)
    try:
        parquet_id = request.form.get("parquet")
        frames = pd.read_parquet(f"gs://speakinghands_cloudbuild/parquets/{parquet_id}.parquet", columns=selected_columns).astype(np.float32)
    except:
        return make_response({"error": f"Parquet '{parquet_id}' not found"}, 404)

    # Crear una instancia de la clase TFLiteModel
    interpreter = tf.lite.Interpreter(str(os.path.abspath("model/model.tflite")))

    with open(str(os.path.abspath("model/character_to_prediction_index.json")), "r") as f:
        character_map = json.load(f)
    rev_character_map = {j:i for i,j in character_map.items()}

    # Predicción
    prediction_fn = interpreter.get_signature_runner("serving_default")
    output = prediction_fn(inputs=frames)
    prediction_str = "".join([rev_character_map.get(s, "") for s in np.argmax(output["outputs"], axis=1)])
    
    # Humanos no detectados
    prediction_str = "No human landmarks detected on uploaded video!" if prediction_str == "4404" else prediction_str

    result = {
        "prediction": prediction_str
    }

    return make_response(result, 200)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))