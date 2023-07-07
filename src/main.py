import os
import json
import pandas as pd
from functools import wraps
from flask_cors import CORS, cross_origin
from flask import Flask, request, make_response
from google.cloud import storage
from datetime import timedelta

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
    Main API function
    """
    return make_response("SpeakingHands API working fine! :)", 200)


@app.route("/upload", methods=["POST"])
@cross_origin()
@login_required
def upload():
    """
    Upload video API URL
    """   
    # Comprobamos
    if 'video' not in request.files or request.files['video'].filename == '':
        return make_response({"error": "You must send a video with the next tag: 'video'"}, 400)

    #Cogemos el archivo
    video = request.files["video"]

    # Guardamos en bucket de GCP
    storage_client = storage.Client()
    bucket = storage_client.get_bucket("speakinghands_cloudbuild")
    blob = bucket.blob(f"uploads/{video.filename}")
    blob.upload_from_string(video.read(), content_type=video.content_type)

    # Extraemos los metadatos del archivo
    blob = bucket.get_blob(f"uploads/{video.filename}")
    metadata = {
        "filename": video.filename,
        "content_type": blob.content_type,
        "size": f"{round((blob.size/1000000), 2)} Mb",
        "update": blob.updated,
        "url": blob.generate_signed_url(version="v4", expiration=timedelta(minutes=1), method="GET")
    }

    return make_response(metadata, 200)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))