from flask import Flask, request, jsonify,json, redirect, current_app
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
# from ..utils import 
from utils import (allowed_file, get_video_transcript, get_response_video, get_response_website, url_validation, system_message_website_incomplete, system_message_video_incomplete, system_message_indepth_lecture_video_incomplete, system_message_indepth_lecture_website_incomplete, get_indepth_lecture_video, get_indepth_lecture_website)
from flask_cors import CORS
from utils_test import LessonPlannerPrompt
from datetime import datetime, timedelta
from sqlalchemy.dialects.postgresql import UUID
import uuid
import enum
import stripe
import PyPDF2
import io
from flask_migrate import Migrate

app = Flask(__name__)
CORS(app)

stripe.api_key = 'sk_test_51OVEYzANOfg5excPWQTVzr98H8KjT5Kv7kSE5ey5PUkE2kZq41PHvjsjiWlWXxHvSGqE00cl5zWiiqDSnYDC328i00OhfIDRW9'
# DATABASE_URI = 'postgresql://postgres:2122@ep-young-truth-30673785.us-east-1.postgres.vercel-storage.com:5432/verceldb'
DATABASE_URI = 'postgresql://postgres:2122@localhost:5432/verceldb'
# psql "postgres://default:HihV04GgcnoO@ep-young-truth-30673785.us-east-1.postgres.vercel-storage.com:5432/verceldb"

YOUR_DOMAIN = 'http://localhost:4242'

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

class SubscriptionType(enum.Enum):
    FREE_DEMO = 1
    MONTHLY = 2
    YEARLY = 3
class User(db.Model):
    __tablename__ = 'users'  # This should match your actual table name in the database
    user_id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    teacher_type = db.Column(db.String(255), nullable=False)
    subscription_type = db.Column(db.Enum(SubscriptionType), default=SubscriptionType.FREE_DEMO)
    subscription_updated_at = db.Column(db.DateTime, default=db.func.current_timestamp())


    def is_demo_active(self):
        return datetime.utcnow() < self.created_at + timedelta(days=2)
    
    def is_subscription_active(self):
        if self.subscription_type == SubscriptionType.MONTHLY:
            return datetime.utcnow() < self.subscription_updated_at + timedelta(days=30)
        elif self.subscription_type == SubscriptionType.YEARLY:
            return datetime.utcnow() < self.subscription_updated_at + timedelta(days=365)
        return False

    def update_subscription(self, subscription_type, subscription_status):
        self.subscription_type = subscription_type
        self.subscription_updated_at = datetime.utcnow()
        db.session.commit()

class Review(db.Model):
    __tablename__ = 'reviews'
    review_id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message = db.Column(db.String(255), nullable=False)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.user_id'), nullable=False)
    gender = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

class ContactUs(db.Model):
    __tablename__ = 'contact_us'
    inquiry_id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
   
@app.route('/')
def home():
    return 'Hello, World again again!'

@app.route('/test', methods=['GET'])
def test():
    return jsonify({'message': 'Hello from Flask!'}), 200

@app.route('/signup', methods=['POST'])
def create_user():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    teacher_type = data.get('teacher_type')
    
    if email is None or password is None:
        return jsonify({'message': 'Missing email or password'}), 400

    if User.query.filter_by(email=email).first() is not None:
        return jsonify({'message': 'User already exists'}), 400

    password_hash = generate_password_hash(password)
    new_user = User(email=email, password_hash=password_hash, teacher_type=teacher_type)

    try:
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'message': 'User created successfully', 'user_id': str(new_user.user_id)}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error creating user'}), 500
        # return jsonify({'message': str(e)}), 500
        # check if the email already exists
        
    
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    teacher_type = data.get('teacher_type')
    
    if email is None or password is None:
        return jsonify({'message': 'Missing email or password'}), 400
    
    user = User.query.filter_by(email=email).first()
    if user and check_password_hash(user.password_hash, password):
        return jsonify({
            'message': 'Logged in successfully',
            'demo_active': user.is_demo_active(),
            'subscription_active': user.is_subscription_active(),
            'subscription_type': user.subscription_type.name,
            'email': user.email,
            'user_id': user.user_id
        }), 200
    else:
        return jsonify({'message': 'Invalid email or password'}), 401

    
@app.route('/lesson-planner', methods=['POST'])
def create_lesson_plan():
    try:
        data = request.json["url"]
        teacher_type = request.json["teacher_type"]

        lesson_planner_prompt = LessonPlannerPrompt(teacher_type).get_prompt()

        system_message_video = lesson_planner_prompt + system_message_video_incomplete
        system_message_website = lesson_planner_prompt + system_message_website_incomplete 

        system_message_indepth_video = lesson_planner_prompt + system_message_indepth_lecture_video_incomplete
        system_message_indepth_website = lesson_planner_prompt + system_message_indepth_lecture_website_incomplete
        validated_url = url_validation(data)
        if validated_url["url"] == "website":
            print("website")
            response = get_response_website(system_message_website, data)
            response_indepth = get_indepth_lecture_website(system_message_indepth_website, data)
            # create a key "in_depth_lecture" and add it to the response
            response["in_depth_lecture"] = response_indepth["in_depth_lecture"]
        elif validated_url["url"] == "youtube":
            print("youtube")
            transcript = get_video_transcript(validated_url["video_url"])
            response = get_response_video(system_message_video, transcript)
            response_indepth = get_indepth_lecture_video(system_message_indepth_video, transcript)
            # create a key "in_depth_lecture" and add it to the response
            response["in_depth_lecture"] = response_indepth["in_depth_lecture"]
        else:
            return jsonify({'message': 'Invalid URL'}), 400
        
        return jsonify(response), 200
    except Exception as e:
        print(e)
        return jsonify({'message': str(e)}), 500
    
@app.route('/pdf-lession-planner', methods=['POST'])
def pdf_lesson_planner():
    try:
        if 'file' not in request.files:
            return jsonify({'message': 'No file part'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'message': 'No selected file'}), 400
        if file and allowed_file(file.filename):
            pdfReader = PyPDF2.PdfFileReader(io.BytesIO(file.read()))
            text = ""
            for page in range(pdfReader.numPages):
                text += pdfReader.getPage(page).extractText()
            teacher_type = request.form["teacher_type"]
    except Exception as e:
        print(e)
        return "Server error", 500       
    


@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    try:
        prices = stripe.Price.list(
            lookup_keys=[request.form['lookup_key']],
            expand=['data.product']
        )
        print(prices)

        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    'price': prices.data[0].id,
                    'quantity': 1,
                },
            ],
            mode='subscription',
            # success_url=f'{YOUR_DOMAIN}/write-review',
            success_url=YOUR_DOMAIN +
            '?success=true&session_id={CHECKOUT_SESSION_ID}',
            cancel_url=YOUR_DOMAIN + '?canceled=true',
        )
        print("checkout success url: " + checkout_session.success_url)
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        print(e)
        return "Server error", 500

@app.route('/create-portal-session', methods=['POST'])
def customer_portal():
    # For demonstration purposes, we're using the Checkout session to retrieve the customer ID.
    # Typically this is stored alongside the authenticated user in your database.
    checkout_session_id = request.form.get('session_id')
    checkout_session = stripe.checkout.Session.retrieve(checkout_session_id)

    # This is the URL to which the customer will be redirected after they are
    # done managing their billing with the portal.
    return_url = YOUR_DOMAIN

    portalSession = stripe.billing_portal.Session.create(
        customer=checkout_session.customer,
        return_url=return_url,
    )
    return redirect(portalSession.url, code=303)


@app.route('/webhook', methods=['POST'])
def webhook_received():
    webhook_secret = 'your-stripe-webhook-secret'  # Set your webhook secret
    request_data = json.loads(request.data)

    if webhook_secret:
        signature = request.headers.get('stripe-signature')
        try:
            event = stripe.Webhook.construct_event(
                payload=request.data, sig_header=signature, secret=webhook_secret)
            data = event['data']
        except Exception as e:
            return jsonify({'error': str(e)}), 400

        event_type = event['type']
        data_object = data['object']

        # Handle the event
        if event_type == 'customer.subscription.updated':
            handle_subscription_updated(data_object)
        elif event_type == 'customer.subscription.deleted':
            handle_subscription_deleted(data_object)

        return jsonify({'status': 'success'}), 200
    else:
        return jsonify({'error': 'Webhook secret not set'}), 500


def handle_subscription_updated(subscription):
    user_email = subscription.get('customer_email')
    subscription_status = subscription.get('status')
    
    # Logic to determine the subscription type based on Stripe data
    subscription_type = determine_subscription_type(subscription)

    user = User.query.filter_by(email=user_email).first()
    if user:
        user.update_subscription(subscription_type, subscription_status)

def handle_subscription_deleted(subscription):
    user_email = subscription.get('customer_email')

    user = User.query.filter_by(email=user_email).first()
    if user:
        user.update_subscription(SubscriptionType.FREE_DEMO, 'canceled')

def determine_subscription_type(subscription):
    price_id = subscription.get('items', {}).get('data', [])[0].get('price', {}).get('id', '')

    if price_id == 'your_monthly_price_id':
        return SubscriptionType.MONTHLY
    elif price_id == 'your_yearly_price_id':
        return SubscriptionType.YEARLY
    else:
        return SubscriptionType.FREE_DEMO  # Default


@app.route('/create-review', methods=['POST'])
def create_review():
    try:
        data = request.get_json()
        message = data.get('message')
        user_id = data.get('user_id')
        gender = data.get('gender')

        if not message or not user_id or not gender:
            return jsonify({'message': 'Missing required fields for review'}), 400

        new_review = Review(message=message, user_id=user_id, gender=gender)
        db.session.add(new_review)
        db.session.commit()

        return jsonify({'message': 'Review created successfully'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error creating review'}), 500

@app.route('/contact-us', methods=['POST'])
def contact_us():
    try:
        data = request.get_json()
        message = data.get('message')
        email = data.get('email')
        name = data.get('name')

        if not message or not email or not name:
            return jsonify({'message': 'Missing required fields for contact form'}), 400

        new_inquiry = ContactUs(message=message, email=email, name=name)
        db.session.add(new_inquiry)
        db.session.commit()

        return jsonify({'message': 'Contact form submitted successfully'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'Error submitting contact form'}), 500


# @app.route('/image-generation', methods=['POST'])
# def create_image():
#     try:
#         data = request.json["image_prompt"]
#         response = get_image(data)
#         return jsonify(response), 200
#     except Exception as e:
#         return jsonify({'message': str(e)}), 500
    

@app.route('/reviews', methods=['GET'])
def get_reviews():
    reviews = Review.query.all()

    review_data = []
    for review in reviews:
        user = User.query.filter_by(user_id=review.user_id).first()

        review_data.append({
            'message': review.message,
            'user_name': user.email if user else None,
        })

    return jsonify(review_data), 200


@app.route('/users/columns', methods=['GET'])
def list_user_columns():
    columns = User.__table__.columns
    column_names = [column.message for column in columns]
    return jsonify(column_names), 200

# @app.route('/about')
# def about():
#     return 'About'

if __name__ == "__main__":
    app.run(debug=True)