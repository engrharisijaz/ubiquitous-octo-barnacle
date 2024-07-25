from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    subject = db.Column(db.String(200), nullable=True)
    password = db.Column(db.String(128), nullable=True)  # Ensure the column exists

def initialize_database():
    with app.app_context():
        db.create_all()
        # Run this part once to alter the table
        if not has_password_column():
            with db.engine.connect() as connection:
                connection.execute(text('ALTER TABLE user ADD COLUMN password VARCHAR(128);'))

def has_password_column():
    # Check if the password column exists
    with db.engine.connect() as connection:
        result = connection.execute(text("PRAGMA table_info(user);"))
        columns = [row[1] for row in result]  # Access the column name using index 1
        return 'password' in columns

if __name__ == '__main__':
    initialize_database()
    app.run(debug=False, host="0.0.0.0", port="5000")
