from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
import logging
import bcrypt
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import base64
import os
from dotenv import load_dotenv
from models import db, User, initialize_database  # Ensure models.py is correctly set up

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# API Key for OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

logging.basicConfig(level=logging.DEBUG)

# SQLAlchemy Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI', 'sqlite:///database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# SMTP Configuration
SMTP_SERVER = os.getenv('SMTP_SERVER')
SMTP_PORT = int(os.getenv('SMTP_PORT', 465))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASS = os.getenv('SMTP_PASS')

@app.route('/questions', methods=['GET'])
def get_questions():
    return jsonify([])  # Placeholder for questions list

@app.route('/generate', methods=['POST'])
def generate_meal_plan():
    try:
        data = request.get_json()
        food_preferences = data.get('preferredMeal')
        servings = data.get('servings')

        if not food_preferences or not servings:
            return jsonify({"error": "Invalid input: preferredMeal and servings are required."}), 400

        meal_plan = ""
        
        for day in range(1, 8):  # Generate for 7 days
            prompt = (f"Create a detailed 1-day meal plan for Day {day} of a {food_preferences} diet with {servings} per meal. "
                      "Meal 1"
                      "[Main Dish Name]"
                      "[Side Dish Name]"

                      "Prep Cook Total"
                      "[prep time][cook time][total time]"

                      "Nutritional Information"
                      "Main Side Total"
                      "Servings [number][number]"
                      "Calories [number][number][number]"
                      "Protein (g) [number][number][number]"
                      "Carb (g) [number][number][number]"
                      "Fiber (g) [number][number][number]"
                      "Fat (g) [number][number][number]"

                      "Ingredients:"
                      "[List of ingredients for main dish]"
                      "-------------------------"
                      "[List of ingredients for side dish]"

                      "Instructions:"
                      "[Numbered list of instructions for main dish]"
                      "-------------------------"
                      "[Instructions for side dish]"

                      "Create a meal plan entry for a healthy chicken dish with a vegetable side"

                      "Only generate for this one day. "
                      "Do not include any extra text, greetings, or conclusions. Stick to the format i provided to you above.")
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a meal planning assistant. Provide only the requested information without any additional text."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000
            )

            day_plan = response['choices'][0]['message']['content'].strip()
            meal_plan += f"\n\nDay {day}:\n{day_plan}"

        return jsonify({"meal_plan": meal_plan.strip()})

    except Exception as e:
        error_message = str(e)
        logging.error('Error generating response: %s', error_message)
        return jsonify({"error": error_message}), 500

@app.route('/')
def home():
    return "Welcome to the MealPlannerDB!"

@app.route('/insert', methods=['POST'])
def insert_documents():
    try:
        data = request.form
        name = data.get('Your Name')
        email = data.get('Email Address')
        phone = data.get('Phone')
        subject = data.get('Subject')

        if not name or not email or not phone or not subject:
            return jsonify({"error": "Invalid input: Name, email, phone, and subject are required."}), 400

        # Check if the user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({"message": "Document with this email already exists"}), 400

        # Create and insert the new user
        new_user = User(name=name, email=email, phone=phone, subject=subject)
        db.session.add(new_user)
        db.session.commit()

        return jsonify({"message": "Document inserted", "id": new_user.id})

    except Exception as e:
        logging.error('Error inserting document: %s', str(e))
        return jsonify({"error": str(e)}), 500

@app.route('/signup', methods=['POST'])
def signup():
    try:
        data = request.form
        name = data.get('Your Name')
        email = data.get('Email Address')
        phone = data.get('Phone', '')  # Default to empty string if not provided
        subject = data.get('Subject', '')  # Default to empty string if not provided
        password = data.get('Password')

        if not name or not email or not password:
            return jsonify({"error": "Invalid input: Name, email, and password are required."}), 400

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({"error": "You already have an account. Please sign in."}), 400

        # Hash the password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        # Create and insert the new user
        new_user = User(name=name, email=email, phone=phone, subject=subject, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        return jsonify({"message": "Account created successfully", "id": new_user.id})

    except Exception as e:
        logging.error('Error during sign-up: %s', str(e))
        return jsonify({"error": str(e)}), 500


@app.route('/show', methods=['GET'])
def show_documents():
    try:
        # Fetch all users
        users = User.query.all()
        user_list = []
        for user in users:
            user_dict = {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'phone': user.phone,
                'subject': user.subject
            }
            user_list.append(user_dict)
        return jsonify(user_list)

    except Exception as e:
        logging.error('Error fetching documents: %s', str(e))
        return jsonify({"error": str(e)}), 500

@app.route('/send-pdf', methods=['POST'])
def send_pdf():
    data = request.json
    email = data.get('email')
    pdf_data = data.get('pdf')

    try:
        # Decode base64 PDF data
        pdf_content = base64.b64decode(pdf_data.split(',')[1])

        # Create email message
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = email
        msg['Subject'] = "Your Meal Plan PDF"

        # Attach the PDF
        pdf_part = MIMEApplication(pdf_content, Name="meal_plan.pdf")
        pdf_part['Content-Disposition'] = 'attachment; filename="meal_plan.pdf"'
        msg.attach(pdf_part)

        # Send the email
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, email, msg.as_string())

        return jsonify({"message": "PDF sent successfully"}), 200

    except Exception as e:
        logging.error('Error sending PDF: %s', str(e))
        return jsonify({"error": str(e)}), 500

@app.route('/send-email', methods=['POST'])
def send_email():
    data = request.get_json()
    
    if not data or not all(k in data for k in ("to", "subject", "body", "pdf_data", "pdf_name")):
        return jsonify({"error": "Invalid input: 'to', 'subject', 'body', 'pdf_data', and 'pdf_name' are required."}), 400
    
    to_address = data['to']
    subject = data['subject']
    body = data['body']
    pdf_data = data['pdf_data']
    pdf_name = data['pdf_name']
    
    try:
        # Decode base64 PDF data
        pdf_content = base64.b64decode(pdf_data)

        # Create email message
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = to_address
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Attach the PDF
        pdf_part = MIMEApplication(pdf_content, Name=pdf_name)
        pdf_part['Content-Disposition'] = f'attachment; filename="{pdf_name}"'
        msg.attach(pdf_part)

        # Send the email
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to_address, msg.as_string())

        return jsonify({"message": "Email sent successfully"}), 200

    except Exception as e:
        logging.error('Error sending email: %s', str(e))
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    initialize_database()
    app.run(debug=False, host="0.0.0.0", port="5000")
