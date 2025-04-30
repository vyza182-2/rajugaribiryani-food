from flask import Flask, render_template, request, redirect, url_for, make_response, jsonify, abort
import pandas as pd
import uuid
import os
from weasyprint import HTML
import requests
from datetime import datetime
from pathlib import Path
import qrcode
import openai

app = Flask(__name__)

# Configuration - REPLACE THESE WITH YOUR ACTUAL VALUES
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


# Restaurant information
RESTAURANT_INFO = {
    "name": "Raju Gari Biryani",
    "cuisine": "Hyderabadi Biryani and Indian Cuisine",
    "hours": "11:00 AM - 11:00 PM daily",
    "address": "123 Biryani Street, Hyderabad",
    "phone": "+91 9876543210",
    "popular_items": ["Chicken Biryani", "Mutton Biryani", "Paneer Biryani"],
    "delivery": "Available via Swiggy and Zomato",
    "specialties": ["Authentic Dum Biryani", "Homemade Spices", "Family Recipes"]
}

# Create a data directory to store files
DATA_DIR = Path('data')
DATA_DIR.mkdir(exist_ok=True, mode=0o775)

# File paths inside the data directory
ORDERS_FILE = DATA_DIR / 'orders.xlsx'
PAYMENTS_FILE = DATA_DIR / 'payments.xlsx'

menu_items = {
    "Chicken Biryani": 180,
    "Mutton Biryani": 250,
    "Paneer Biryani": 160,
    "Veg Biryani": 140,
    "Egg Biryani": 150,
    "Chicken Fried Rice": 120,
    "Mutton Fried Rice": 180,
    "Paneer Fried Rice": 150,
    "Veg Fried Rice": 120,
    "Egg Fried Rice": 130,
    "Chicken Korma": 150,
    "Mutton Korma": 200,
    "Paneer Korma": 170,
    "Veg Korma": 140,
    "Egg Korma": 150,
    "Chicken Tikka": 160,
    "Mutton Tikka": 220,
    "Paneer Tikka": 180,
    "Veg Tikka": 150,
    "Egg Tikka": 160,
    "Chicken Tandoori": 170,
    "Mutton Tandoori": 230,
    "Paneer Tandoori": 190,
}

# Initialize Excel files with proper permissions
def init_excel_files():
    """Initializes Excel files for orders and payments"""
    if not ORDERS_FILE.exists():
        pd.DataFrame(columns=["Order ID", "Name", "Phone", "Items", "Total"]).to_excel(ORDERS_FILE, index=False)

    if not PAYMENTS_FILE.exists():
        pd.DataFrame(columns=["Order ID", "Amount", "Payment Time", "Method"]).to_excel(PAYMENTS_FILE, index=False)

# Initialize files at startup
init_excel_files()

def generate_upi_qr(order_id, amount):
    """Generate a UPI QR code for the order"""
    upi_id = "vyza.18@kotak"  # Your restaurant's UPI ID
    upi_link = f"upi://pay?pa={upi_id}&pn=Raju%20Gari%20Biryani&am={amount}&cu=INR"

    qr_dir = "static"
    os.makedirs(qr_dir, exist_ok=True)
    qr_filename = f"qr_{order_id}.png"
    qr_path = os.path.join(qr_dir, qr_filename)

    qrcode.make(upi_link).save(qr_path)
    return qr_filename

def save_to_excel(file_path, new_data):
    """Save new data to Excel file"""
    try:
        if file_path.exists():
            df = pd.read_excel(file_path)
        else:
            df = pd.DataFrame(columns=new_data.keys())
        df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
        df.to_excel(file_path, index=False)
        return True
    except Exception as e:
        print(f"Error saving to {file_path}: {e}")
        return False

def send_telegram_message(message):
    """Send message via Telegram bot"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials not configured")
        return False
        
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown'
        }
        response = requests.post(url, data=payload, timeout=5)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/menu')
def menu():
    return render_template('menu.html', menu=menu_items)

@app.route('/order', methods=['POST'])
def order():
    data = request.form
    name = data.get("name", "").strip()
    phone = data.get("phone", "").strip()

    if not name:
        return "Name is required", 400

    selected_items = {item: int(data.get(item, 0)) for item in menu_items}
    selected_items = {k: v for k, v in selected_items.items() if v > 0}

    if not selected_items:
        return "No items selected", 400

    total = sum(menu_items[item] * qty for item, qty in selected_items.items())
    order_id = str(uuid.uuid4())[:8]

    order_data = {
        "Order ID": order_id,
        "Name": name,
        "Phone": phone,
        "Items": str(selected_items),
        "Total": total
    }

    if not save_to_excel(ORDERS_FILE, order_data):
        return "Error saving order", 500

    items_text = "\n".join([f"• {item} x{qty} (₹{menu_items[item]*qty})" 
                          for item, qty in selected_items.items()])
    message = f"""
📦 *New Order Received* 🍽️
🆔 *Order ID*: `{order_id}`
👤 *Customer*: {name}
📞 *Phone*: {phone or 'Not provided'}
📝 *Items*:
{items_text}
💰 *Total*: ₹{total}
"""
    send_telegram_message(message)

    return redirect(url_for("payment", order_id=order_id, total=total))

@app.route('/payment')
def payment():
    order_id = request.args.get("order_id")
    total = request.args.get("total")

    if not order_id or not total:
        return redirect(url_for('menu'))

    qr_filename = generate_upi_qr(order_id, total)

    return render_template("payment.html", 
                         order_id=order_id, 
                         total=total,
                         qr_filename=qr_filename,
                         payment_methods=["UPI", "Credit Card", "Cash on Delivery"])

@app.route('/confirm_payment', methods=['POST'])
def confirm_payment():
    order_id = request.form.get('order_id')
    amount = request.form.get('amount')
    payment_method = request.form.get('payment_method', 'Unknown')

    if not order_id or not amount:
        return "Missing payment details", 400

    time_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    payment_data = {
        "Order ID": order_id,
        "Amount": amount,
        "Payment Time": time_now,
        "Method": payment_method
    }

    if not save_to_excel(PAYMENTS_FILE, payment_data):
        return "Error saving payment", 500

    message = f"""
💳 *Payment Confirmed* ✅
🆔 *Order ID*: `{order_id}`
💰 *Amount Paid*: ₹{amount}
💸 *Method*: {payment_method}
⏰ *Time*: {time_now}
"""
    send_telegram_message(message)

    return render_template("confirmation.html", 
                         order_id=order_id, 
                         amount=amount,
                         payment_time=time_now)

@app.route('/invoice/<order_id>')
def download_invoice(order_id):
    print(f"\n--- Attempting to generate invoice for {order_id} ---")
    
    # Check file existence
    print(f"Orders file exists: {ORDERS_FILE.exists()}")
    print(f"Payments file exists: {PAYMENTS_FILE.exists()}")
    
    try:
        # Load data
        orders_df = pd.read_excel(ORDERS_FILE)
        payments_df = pd.read_excel(PAYMENTS_FILE)
        print("Excel files loaded successfully")
        
        # Debug: Print all order IDs
        print("All order IDs in orders.xlsx:")
        print(orders_df['Order ID'].tolist())
        
        # Find order
        order_match = orders_df[orders_df['Order ID'].astype(str) == order_id]
        print(f"\nFound {len(order_match)} matching orders")
        
        if order_match.empty:
            print(f"ERROR: Order {order_id} not found in orders.xlsx")
            abort(404)
            
        order = order_match.iloc[0].to_dict()
        print("\nOrder data:")
        print(order)
        
        # Find payment
        payment_match = payments_df[payments_df['Order ID'].astype(str) == order_id]
        print(f"\nFound {len(payment_match)} matching payments")
        
        if payment_match.empty:
            print(f"ERROR: Payment for order {order_id} not found")
            abort(404)
            
        payment = payment_match.iloc[0].to_dict()
        print("\nPayment data:")
        print(payment)
        
        # Generate PDF
        print("\nAttempting to render template...")
        html = render_template('invoice_template.html', 
                             order=order, 
                             payment=payment,
                             RESTAURANT_INFO=RESTAURANT_INFO)
        print("Template rendered successfully")
        
        print("\nGenerating PDF...")
        pdf = HTML(string=html).write_pdf()
        print("PDF generated successfully")
        
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=invoice_{order_id}.pdf'
        return response
        
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        abort(404, description=str(e))

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')

        telegram_message = f"""
        *New Contact Us Message* 📩
        
        *Name*: {name}
        *Email*: {email}
        *Message*: 
        {message}
        """
        send_telegram_message(telegram_message)

        return render_template('contact_success.html', name=name)

    return render_template('contact.html')

@app.route('/customer-support')
def customer_support():
    return render_template('customer_chat.html')

# Common questions and answers
COMMON_QUESTIONS = {
    # ... (keep your existing COMMON_QUESTIONS dictionary) ...
    "i want discount|discount|offer|deal|sale":"If you asking discount or you can do something, focus on your career, and then buy our biryani.",
    "i want free biryani|free|give me free|give me free biryani|free biryani":"If you asking free biryani or you can do something, focus on your career, and then buy our biryani.",
    "i want free delivery|free delivery|give me free delivery|give me free delivery":"If you asking free delivery or you can do something, focus on your career, and then buy our biryani.",
    "i want free food|free food|give me free food|give me free food":"If you asking free food or you can do something, focus on your career, and then buy our biryani.",
    "i want free meal|free meal|give me free meal|give me free meal":"If you asking free meal or you can do something, focus on your career, and then buy our biryani.",
    "i want free biryani|free biryani|give me free biryani|give me free biryani":"If you asking free biryani or you can do something. Focus on your career then buy our biryani.",
    "i want free meal|free meal|give me free meal|give me free meal":"If you asking free meal or you can do something, focus on your career, and then buy our biryani.",
    "i want free biryani|free biryani|give me free biryani|give me free biryani":"If you asking free biryani or you can do something, focus on your career, and then buy our biryani.",
    "expensive|price|to cost|expensive|high price|hihg cost":"Our biryani is expensive, or you can do something focus on your career and then buy our biryani.",
    "timings|hours|open|close|time": "We're open daily from 11:00 AM to 11:00 PM",
    "address|location|where|place": "We're located at 123 Biryani Street, Hyderabad",
    "phone|number|contact|call": "Call us at +91 9876543210",
    "menu|items|serve|food|dishes": "We specialize in Hyderabadi biryanis including Chicken, Mutton, Paneer, Veg and Egg varieties. Our full menu is available on our website.",
    "delivery|order online|swiggy|zomato": "We deliver via Swiggy and Zomato",
    "famous|signature|popular|best": "Our Chicken Dum Biryani is our most famous dish, cooked with authentic spices and dum technique",
    "price|cost|how much": "Our biryanis range from ₹140 to ₹250. Chicken starts at ₹180, Mutton at ₹250",
    "parking|car|vehicle": "We have limited parking space available in front of the restaurant",
    "reservation|book table|reserve": "Call us directly at +91 9876543210 to reserve a table",
    "vegetarian|veg options|veg": "We have excellent vegetarian options including Paneer Biryani (₹160) and Veg Biryani (₹140)",
    "about|story|history": "Raju Gari Biryani has been serving authentic Hyderabadi biryani since 1985 using family recipes",
    "payment|pay|cash|card": "We accept UPI, Credit Cards, and Cash on Delivery",
    "special|signature|dish|famous": "Our Chicken Dum Biryani is our most popular dish, cooked with authentic spices and dum technique",
    "spices|ingredients|fresh|quality": "We use only the freshest ingredients and homemade spices in our dishes",
    "service|staff|waiter|waitress": "Our staff is friendly and attentive, always ready to help you with your order",
    "reviews|rating|customer|feedback": "You can read customer reviews and ratings on Swiggy and Zomato",
    "catering|events|party|wedding": "We offer catering services for events and parties. Please call us for more details",
    "specials|offers|discounts|deals": "Check our website or social media for current specials and offers",
    "expensive|price|to cost|expensive|high price|hihg cost":"Our biryani is expensive, or you can do something, focus on your career, and then buy our biryani.",
    "i want discount|discount|offer|deal|sale":"If you asking discount or you can do something, focus on your career, and then buy our biryani.",
    "i want free biryani|free|give me free|give me free biryani|free biryani":"If you asking free biryani or you can do something, focus on your career, and then buy our biryani.",
    "i want free delivery|free delivery|give me free delivery|give me free delivery":"If you asking free delivery or you can do something, focus on your career, and then buy our biryani.",
    "i want free food|free food|give me free food|give me free food":"If you asking free food or you can do something, focus on your career, and then buy our biryani.",
    "i want free meal|free meal|give me free meal|give me free meal":"If you asking free meal or you can do something, focus on your career, and then buy our biryani.",
    "i want free biryani|free biryani|give me free biryani|give me free biryani":"If you asking free biryani or you can do something. Focus on your career then buy our biryani.",
    "i want free meal|free meal|give me free meal|give me free meal":"If you asking free meal or you can do something, focus on your career, and then buy our biryani.",
    "i want free biryani|free biryani|give me free biryani|give me free biryani":"If you asking free biryani or you can do something, focus on your career, and then buy our biryani.",
    "i want free meal|free meal|give me free meal|give me free meal":"If you asking free meal or you can do something, focus on your career, and then buy our biryani.",
    "free food|free food|give me free food|give me free food":"If you asking free food or you can do something, focus on your career, and then buy our biryani.",
    "hi|hello|hey|greetings":"Hello! Welcome to Raju Gari Biryani. How can I help you today?",
    "thank you|thanks|appreciate|grateful":"You're welcome! If you have any more questions, feel free to ask.",
    "bye|goodbye|see you|take care":"Goodbye! Have a great day!",
    "help|support|assistance|aid":"How can I assist you? Please ask your question.",
    "location|address|where|find":"Raju Gari Biryani is located at 123 Main Street, Hyderabad, India. You can find us easily with Google Maps.",
    "contact|phone|email|contact information":"You can call us at +91 9876543210 or email us at info@rajugaribiryani.com for any inquiries.",
    "hours|timings|open|close|working hours":"We are open from 11:00 AM to 11:00 PM every day.",
    "menu|food|dishes|items":"We serve a variety of biryanis, curries, and Indian dishes. Check our menu for details.",
    "price|cost|expensive|cheap|affordable":"Our dishes are reasonably priced. Please check our menu for prices.",
    "delivery|takeout|order|eat in":"We offer delivery and takeout services. Please place your order through our website or call us directly.",
    "reservation|book|table|seating":"You can reserve a table by calling us at +91 9876543210 or through our website.",
    "catering|events|party|wedding":"We provide catering services for events and parties. Please contact us for more details.",
    "reviews|rating|customer|feedback":"You can read customer reviews and ratings on Swiggy and Zomato.",
    "specials|offers|discounts|deals":"Check our website or social media for current specials and offers.",
    "vegetarian|vegan|veg|non-veg":"We have vegetarian and non-vegetarian options available. Please check our menu.",
    "spicy|mild|flavor|taste":"Our biryanis are flavorful and can be made spicy or mild based on your preference.",
    "ingredients|fresh|quality|spices":"We use only the freshest ingredients and homemade spices in our dishes.",
    "parking|car|vehicle":"We have limited parking space available in front of the restaurant.",
    "reservation|book table|reserve":"Call us directly at +91 9876543210 to reserve a table",
    "vegetarian|veg options|veg":"We have excellent vegetarian options including Paneer Biryani (₹160) and Veg Biryani (₹140)",
    "about|story|history":"Raju Gari Biryani has been serving authentic Hyderabadi biryani since 1985 using family recipes",
    "payment|pay|cash|card":"We accept UPI, Credit Cards, and Cash on Delivery",
    "special|signature|dish|famous":"Our Chicken Dum Biryani is our most popular dish, cooked with authentic spices and dum technique", 
    "recommend|suggest|popular|best":"Our Chicken Dum Biryani is our most popular dish, cooked with authentic spices and dum technique",
    "delivery|takeout|order|eat in":"We offer delivery and takeout services. Please place your order through our website or call us directly",
    "reservation|book|table|seating":"You can reserve a table by calling us at +91 9876543210 or through our website",
}

def find_answer(question):
    question = question.lower()
    for keywords, answer in COMMON_QUESTIONS.items():
        if any(keyword in question for keyword in keywords.split("|")):
            return answer
    return "Thank you for your question! For more details, please call us at +91 9876543210"

def generate_ai_response(customer_query):
    """Generate response to customer queries using AI"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"""
                You are a helpful assistant for {RESTAURANT_INFO['name']}, a Hyderabadi biryani restaurant.
                Always respond in friendly, casual tone. Keep answers concise (1-2 sentences max).
                Never make up information - if unsure, say to contact the restaurant.
                
                Restaurant Info:
                - Name: {RESTAURANT_INFO['name']}
                - Cuisine: {RESTAURANT_INFO['cuisine']}
                - Hours: {RESTAURANT_INFO['hours']}
                - Address: {RESTAURANT_INFO['address']}
                - Phone: {RESTAURANT_INFO['phone']}
                - Popular Items: {', '.join(RESTAURANT_INFO['popular_items'])}
                - Specialties: {', '.join(RESTAURANT_INFO['specialties'])}
                """},
                {"role": "user", "content": customer_query}
            ],
            temperature=0.7,
            max_tokens=150
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"OpenAI Error: {str(e)}")
        raise

@app.route('/ask', methods=['POST'])
def handle_customer_query():
    customer_query = request.json.get('query', '')
    if not customer_query:
        return jsonify({"error": "Please provide a question"}), 400
    
    # First try predefined answers
    answer = find_answer(customer_query)
    if answer:
        return jsonify({"response": answer})
    
    # Then try AI
    try:
        response = generate_ai_response(customer_query)
        return jsonify({"response": response})
    except Exception as e:
        print(f"Error handling query: {e}")
        return jsonify({"response": "I'm having trouble answering that. Please call us at +91 9876543210 for assistance."})

# Print all routes for debugging
print("Registered routes:")
for rule in app.url_map.iter_rules():
    print(rule)



if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)