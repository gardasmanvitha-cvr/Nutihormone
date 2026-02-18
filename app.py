import os
from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import google.generativeai as genai
from google.generativeai import GenerativeModel
from datetime import datetime

import PyPDF2

app = Flask(__name__)
CORS(app)

# ✅ CONFIGURATION
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:Manvitha@localhost/nutrihormone'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.secret_key = "secure_key_123"

# ✅ GOOGLE GEMINI AI CONFIGURATION
# You must get a key from https://aistudio.google.com/
GOOGLE_API_KEY = "AIzaSyCFrkQmV7SS0kIklQhl3yPE5rR8QK8NoJw"
genai.configure(api_key=GOOGLE_API_KEY)

db = SQLAlchemy(app)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ===================== DATABASE MODELS =====================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    
    # Store the AI generated plan here so it persists on refresh
    latest_plan = db.Column(db.Text, nullable=True) 
class Cycle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(120))
    last_period = db.Column(db.Date)
    cycle_length = db.Column(db.Integer)

# ===================== HELPER FUNCTIONS =====================
def extract_text_from_pdf(pdf_path):
    text = ""
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        for page in reader.pages:
            text += page.extract_text()
    return text

def get_ai_recommendation(medical_text, wellness_goal):
    prompt = f"""
    You are an expert nutritionist and health analyst.

    A user has uploaded a medical/health report.
    Their primary wellness goal is: {wellness_goal}.

    Analyze the report ONLY for general health markers
    (nutrition, vitamins, minerals, metabolic indicators).

    Provide:
    1. Nutritional Strategy (foods to include / limit)
    2. Lifestyle & Activity Advice (safe, non-medical)
    3. One Key Health Insight

    ❗ Important rules:
    - Do NOT diagnose diseases
    - Do NOT prescribe medication
    - Do NOT alarm the user
    - Encourage consulting a healthcare professional

    Medical Report Content:
    {medical_text[:3000]}
    
    Format output in clean HTML using <b>, <ul>, <li> only.
    """

    # ✅ CREATE GEMINI MODEL OBJECT (THIS FIXES THE ERROR)
    model = GenerativeModel("gemini-1.5-pro")


    response = model.generate_content(prompt)

    return response.text

# ===================== ROUTES =====================
@app.route('/')
def home(): return render_template('index.html')

@app.route('/login-page')
def login_page(): return render_template('login.html')

@app.route('/signup-page')
def signup_page(): return render_template('signup.html')

@app.route('/dashboard')
def dashboard(): return render_template('dashboard.html')

@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    if User.query.filter_by(email=data.get('email')).first():
        return jsonify({"error": "Email exists"}), 409
    hashed_pw = generate_password_hash(data.get('password'), method='pbkdf2:sha256')
    new_user = User(name=data.get('name'), email=data.get('email'), password=hashed_pw)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "User created"}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user = User.query.filter_by(email=data.get('email')).first()
    if not user or not check_password_hash(user.password, data.get('password')):
        return jsonify({"error": "Invalid credentials"}), 401
    return jsonify({"name": user.name, "email": user.email, "id": user.id}), 200

# ✅ AI UPLOAD ENDPOINT
@app.route('/analyze-health', methods=['POST'])
def analyze_health():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    user_email = request.form.get('email')
    wellness_goal = request.form.get('wellness_goal', 'General Health')

    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # 1. Read PDF
        medical_text = extract_text_from_pdf(filepath)

        # 2. Get AI Insight
        try:
            ai_plan = get_ai_recommendation(medical_text, wellness_goal)
            
            # 3. Save to DB (Optional: Update user record)
            user = User.query.filter_by(email=user_email).first()
            if user:
                user.latest_plan = ai_plan
                db.session.commit()

            return jsonify({"plan": ai_plan}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500
@app.route("/save-cycle", methods=["POST"])
def save_cycle():
    data = request.get_json()

    cycle = Cycle(
        user_email=None,  # later link to logged-in user
        last_period=datetime.fromisoformat(data["last_period"]),
        cycle_length=data["cycle_length"]
    )

    db.session.add(cycle)
    db.session.commit()

    return jsonify({"message": "Cycle data saved"}), 200
@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/cycle-tracker')
def cycle_tracker():
    return render_template('cycle.html')

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)