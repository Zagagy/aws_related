from flask import Flask, render_template, request, jsonify
import base64
import boto3
import json
from flask_cors import CORS

# Flask app setup
app = Flask(__name__, template_folder="templates")
CORS(app)

# AWS setup
MODEL_VERSION = "anthropic.claude-3-haiku-20240307-v1:0"
ANTHROPHIC_VERSION = "bedrock-2023-05-31"

# Bedrock client setup
bedrock_client = boto3.client(service_name="bedrock-runtime")

def encode_image(file):
    image_bytes = file.read()
    return base64.b64encode(image_bytes).decode("utf-8")

def call_model(prompt, encoded_image):
    body = {
        "anthropic_version": ANTHROPHIC_VERSION,
        "max_tokens": 1000,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": encoded_image,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            }
        ],
    }

    response = bedrock_client.invoke_model(
        modelId=MODEL_VERSION,
        body=json.dumps(body)
    )
    response_body = json.loads(response["Body"].read())
    return response_body

@app.route('/upload', methods=['POST'])
def upload_file_post():
    if request.method == 'POST':
        encoded_image = request.files['image']
        prompt = request.form['prompt']
        response = call_model(prompt, encoded_image)
        return jsonify(response)
    else:
        return jsonify({"error": "Invalid request method."}), 405



@app.route('/')
def home():
    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True)
