from flask import Flask, request, send_file, jsonify
from io import BytesIO
import barcode
from barcode.writer import ImageWriter
from fpdf import FPDF
import requests
import json
from firebase_admin import credentials, firestore, initialize_app
from flask_cors import CORS
import os
from PIL import ImageFont  # Adjusting font handling for errors

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize Firebase
firebase_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")  # Fetch credentials from environment variables
if firebase_credentials:
    cred = credentials.Certificate(json.loads(firebase_credentials))  # Parse JSON from env variable
    initialize_app(cred)
    db = firestore.client()
else:
    raise ValueError("Firebase credentials not found in environment variables.")

@app.route('/generate_pass', methods=['POST'])
def generate_pass():
    print("Received data:", request.json)
    try:
        # Step 1: Get Data from Webhook
        data = request.json
        name = data.get('name')
        phone = data.get('phone')
        picture_url = data.get('picture')  # URL to the user's picture

        if not name or not phone:
            return jsonify({"error": "Missing required form fields"}), 400
        
        unique_id = phone  # Use phone number or generate your own unique ID

        # Step 2: Generate Barcode
        barcode_file = BytesIO()
        barcode_obj = barcode.Code128(unique_id, writer=ImageWriter())
        barcode_obj.write(barcode_file)
        barcode_file.seek(0)

        # Step 3: Create Festival Pass PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt="Festival Pass", ln=True, align='C')
        pdf.cell(200, 10, txt=f"Name: {name}", ln=True)
        pdf.cell(200, 10, txt=f"Phone: {phone}", ln=True)
        pdf.image(barcode_file, x=10, y=40, w=100)

        # Optional: Add User's Picture
        if picture_url:
            response = requests.get(picture_url)
            if response.status_code == 200:
                picture_file = BytesIO(response.content)
                pdf.image(picture_file, x=10, y=90, w=100)
            else:
                pdf.cell(200, 10, txt="Picture could not be loaded", ln=True)

        # Step 4: Save PDF
        pdf_output = BytesIO()
        pdf.output(pdf_output)
        pdf_output.seek(0)

        # Step 5: Store Data in Firebase
        pass_data = {
            "unique_id": unique_id,
            "name": name,
            "phone": phone,
            "picture_url": picture_url,
            "barcode_data": unique_id
        }
        db.collection('festival_passes').document(unique_id).set(pass_data)

        # Step 6: Return Festival Pass as Download
        return send_file(pdf_output, mimetype='application/pdf', as_attachment=True, download_name="festival_pass.pdf")

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Verification Endpoint (Optional)
@app.route('/verify_pass', methods=['POST'])
def verify_pass():
    try:
        scanned_code = request.json['code']
        doc = db.collection('festival_passes').document(scanned_code).get()

        if doc.exists:
            return jsonify({"status": "valid", "details": doc.to_dict()})
        else:
            return jsonify({"status": "invalid", "message": "Pass not found"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(port=5000, debug=True)
