from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from models import db, User, Product, Order
from payment import initiate_orange_money, initiate_mvola, check_payment_status
import os
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'votre-secret-key-changez-moi'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///shop.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# ---- Decorator login required ----
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

# ---- Routes principales ----
@app.route('/')
def index():
    products = Product.query.all()
    return render_template('index.html', products=products)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']
        if User.query.filter_by(email=email).first():
            flash('Email efa ampiasaina!', 'error')
            return redirect(url_for('register'))
        user = User(name=name, email=email, phone=phone)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Vita ny fisoratana anarana!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['user_name'] = user.name
            flash('Tonga soa!', 'success')
            return redirect(url_for('dashboard'))
        flash('Email na teny miafina diso!', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    user = User.query.get(session['user_id'])
    orders = Order.query.filter_by(user_id=user.id).order_by(Order.created_at.desc()).all()
    return render_template('dashboard.html', user=user, orders=orders)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('product_detail.html', product=product)

@app.route('/checkout/<int:product_id>', methods=['GET', 'POST'])
@login_required
def checkout(product_id):
    product = Product.query.get_or_404(product_id)
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        payment_method = request.form['payment_method']
        phone = request.form['phone']
        order = Order(
            user_id=user.id,
            product_id=product.id,
            amount=product.price,
            payment_method=payment_method,
            phone=phone,
            status='pending'
        )
        db.session.add(order)
        db.session.commit()
        # Initier le paiement
        if payment_method == 'orange_money':
            result = initiate_orange_money(phone, product.price, order.id)
        else:
            result = initiate_mvola(phone, product.price, order.id)
        if result['success']:
            order.transaction_ref = result.get('transaction_ref', '')
            db.session.commit()
            return redirect(url_for('payment_pending', order_id=order.id))
        else:
            flash('Nisy olana tamin\'ny payment. Andramo indray.', 'error')
    return render_template('checkout.html', product=product, user=user)

@app.route('/payment/pending/<int:order_id>')
@login_required
def payment_pending(order_id):
    order = Order.query.get_or_404(order_id)
    product = Product.query.get(order.product_id)
    return render_template('payment_pending.html', order=order, product=product)

@app.route('/payment/check/<int:order_id>')
@login_required
def check_payment(order_id):
    order = Order.query.get_or_404(order_id)
    status = check_payment_status(order.transaction_ref, order.payment_method)
    if status == 'completed':
        order.status = 'completed'
        order.paid_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'status': 'completed', 'download_url': url_for('download_product', order_id=order.id)})
    elif status == 'failed':
        order.status = 'failed'
        db.session.commit()
        return jsonify({'status': 'failed'})
    return jsonify({'status': 'pending'})

@app.route('/download/<int:order_id>')
@login_required
def download_product(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != session['user_id'] or order.status != 'completed':
        flash('Tsy afaka midina ianao.', 'error')
        return redirect(url_for('dashboard'))
    product = Product.query.get(order.product_id)
    return render_template('download.html', product=product, order=order)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Mamorona produits demo raha tsy misy
        if not Product.query.first():
            demo_products = [
                Product(name='LogiPro Suite', description='Logiciel gestion orinasa komplet', price=15000, file_url='/files/logipro.zip', image='💼'),
                Product(name='DesignMG', description='Application creation graphique ho an\'ny Malagasy', price=25000, file_url='/files/designmg.zip', image='🎨'),
                Product(name='ComptaMada', description='Logiciel comptabilite malagasy', price=35000, file_url='/files/comptamada.zip', image='📊'),
            ]
            for p in demo_products:
                db.session.add(p)
            db.session.commit()
    app.run(debug=True)
