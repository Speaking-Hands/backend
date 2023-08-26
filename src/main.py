from utils.functions import *
from model import *
import os
import cv2
import json
import tempfile
import mediapipe as mp
import tensorflow as tf
import wordninja
from functools import wraps
from flask_cors import CORS, cross_origin
from flask import Flask, request, make_response
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


@app.route("/predict", methods=["POST"])
@cross_origin()
@login_required
def predict():

    # -- Comprobamos video --
    if 'video' not in request.files or request.files['video'].filename == '':
        return make_response({"error": "You must send a video with the next tag: 'video'"}, 400)
    
    video = request.files["video"]

    if video.content_type.split("/")[0] != "video":
        return make_response({"error": "File uploaded is not a video"}, 400)
    
    print(f"Realizando predicción del video: {video.filename}")
    with tempfile.TemporaryDirectory() as td:

        # -- Recuperamos todos los frames del video --
        temp_filename = Path(td) / 'uploaded_video'
        request.files['video'].save(temp_filename)

        mp_holistic = mp.solutions.holistic
        cap = cv2.VideoCapture(str(temp_filename))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        parquet_row_list = []

        with mp_holistic.Holistic(static_image_mode=False, model_complexity=1) as holistic:
            print(f"Número de frames a procesar: {total_frames}")
            # -- Calculamos puntos de referencia --
            for frame_num in range(total_frames):
                ret, frame = cap.read()
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = holistic.process(frame_rgb)
                frame_row_result = create_frame_row(frame_num, results)
                parquet_row_list.append(frame_row_result)
                print(f"{frame_num} / {total_frames} frames procesados!") if frame_num % 50 == 0 else None
            
            # -- Transformamos a "parquet" (creamos el dataframe directamente con los resultados de todos los frames) --
            parquet = pd.concat(parquet_row_list, axis=0)

        cap.release() 

    # -- Predecimos los resultados utilizando modelo --

    # Leer el archivo 'inference_args.json' para obtener las columnas seleccionadas
    with open(str(os.path.abspath("model/inference_args.json")), 'r') as f:
        inference_args = json.load(f)
    selected_columns = inference_args['selected_columns']
    
    # Frames video (parquet)
    frames = parquet.copy()[selected_columns].astype(np.float32)

    # Crear una instancia de la clase TFLiteModel
    interpreter = tf.lite.Interpreter(str(os.path.abspath("model/model.tflite")))

    with open(str(os.path.abspath("model/character_to_prediction_index.json")), "r") as f:
        character_map = json.load(f)
    rev_character_map = {j:i for i,j in character_map.items()}

    # Predicción
    prediction_fn = interpreter.get_signature_runner("serving_default")
    output = prediction_fn(inputs=frames)
    prediction_str = "".join([rev_character_map.get(s, "") for s in np.argmax(output["outputs"], axis=1)])
    
    # Procesar resultado 
    prediction_str = " ".join(wordninja.split(prediction_str))
    
    # No humans detected
    prediction_str = "No human landmarks detected on uploaded video!" if prediction_str in ["2 a e a roe", "a roe"] else prediction_str


    print(f"Predicción obtenida del video: {prediction_str}")
    result = {
        "prediction": prediction_str
    }
    return make_response(result, 200)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))