from flask import Flask, render_template, request, jsonify, session, send_from_directory
from functools import wraps
import hashlib
from datetime import datetime
import os
import json

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

DATA_FILE = 'users.json'

def load_users():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_users():
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения: {e}")

users = load_users()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return jsonify({'error': 'Не авторизован'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    name = data.get('name')
    password = data.get('password')
    
    if not email or not name or not password:
        return jsonify({'error': 'Все поля обязательны'}), 400
    
    if email in users:
        return jsonify({'error': 'Пользователь уже существует'}), 400
    
    users[email] = {
        'email': email,
        'name': name,
        'password': hash_password(password),
        'balance': 0,
        'transactions': [],
        'goals': [],
        'avatar': None
    }
    
    save_users()
    
    session['user_email'] = email
    session['user_name'] = name
    
    return jsonify({
        'success': True,
        'user': {
            'email': email,
            'name': name,
            'balance': users[email]['balance'],
            'transactions': users[email]['transactions'],
            'goals': users[email]['goals'],
            'avatar': users[email]['avatar']
        }
    })

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'error': 'Email и пароль обязательны'}), 400
    
    if email not in users:
        return jsonify({'error': 'Неверный email или пароль'}), 401
    
    if users[email]['password'] != hash_password(password):
        return jsonify({'error': 'Неверный email или пароль'}), 401
    
    session['user_email'] = email
    session['user_name'] = users[email]['name']
    
    return jsonify({
        'success': True,
        'user': {
            'email': email,
            'name': users[email]['name'],
            'balance': users[email]['balance'],
            'transactions': users[email]['transactions'],
            'goals': users[email]['goals'],
            'avatar': users[email]['avatar']
        }
    })

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/transactions', methods=['POST'])
@login_required
def add_transaction():
    data = request.get_json()
    email = session['user_email']
    
    transaction = {
        'id': int(datetime.now().timestamp() * 1000),
        'amount': float(data.get('amount')),
        'type': data.get('type'),
        'category': data.get('category'),
        'date': data.get('date', datetime.now().isoformat()),
        'card': data.get('card', 'Основной')
    }
    
    users[email]['transactions'].insert(0, transaction)
    
    if transaction['type'] == 'income':
        users[email]['balance'] += transaction['amount']
    else:
        users[email]['balance'] -= transaction['amount']
    
    save_users()
    
    return jsonify({'success': True, 'transaction': transaction, 'balance': users[email]['balance']})

@app.route('/api/transactions/<int:trans_id>', methods=['DELETE'])
@login_required
def delete_transaction(trans_id):
    email = session['user_email']
    
    transactions = users[email]['transactions']
    for i, t in enumerate(transactions):
        if t['id'] == trans_id:
            if t['type'] == 'income':
                users[email]['balance'] -= t['amount']
            else:
                users[email]['balance'] += t['amount']
            del transactions[i]
            break
    
    save_users()
    
    return jsonify({'success': True, 'balance': users[email]['balance']})

@app.route('/api/goals', methods=['POST'])
@login_required
def add_goal():
    data = request.get_json()
    email = session['user_email']
    
    goal = {
        'id': int(datetime.now().timestamp() * 1000),
        'name': data.get('name'),
        'target': float(data.get('target')),
        'current': float(data.get('current', 0))
    }
    
    users[email]['goals'].append(goal)
    save_users()
    
    return jsonify({'success': True, 'goal': goal})

@app.route('/api/goals/<int:goal_id>', methods=['PUT'])
@login_required
def update_goal(goal_id):
    data = request.get_json()
    email = session['user_email']
    
    for goal in users[email]['goals']:
        if goal['id'] == goal_id:
            if 'name' in data:
                goal['name'] = data['name']
            if 'target' in data:
                goal['target'] = float(data['target'])
            if 'current' in data:
                goal['current'] = float(data['current'])
            break
    
    save_users()
    
    return jsonify({'success': True})

@app.route('/api/goals/<int:goal_id>/add', methods=['POST'])
@login_required
def add_to_goal(goal_id):
    data = request.get_json()
    email = session['user_email']
    amount = float(data.get('amount', 0))
    
    if amount <= 0:
        return jsonify({'error': 'Сумма должна быть больше 0'}), 400
    
    goal = None
    for g in users[email]['goals']:
        if g['id'] == goal_id:
            goal = g
            break
    
    if not goal:
        return jsonify({'error': 'Цель не найдена'}), 404
    
    if users[email]['balance'] < amount:
        return jsonify({'error': f'Недостаточно средств. Доступно: {users[email]["balance"]} ₽'}), 400
    
    new_current = goal['current'] + amount
    if new_current > goal['target']:
        return jsonify({'error': f'Сумма превышает цель. Осталось: {goal["target"] - goal["current"]} ₽'}), 400
    
    users[email]['balance'] -= amount
    goal['current'] = new_current
    
    transaction = {
        'id': int(datetime.now().timestamp() * 1000),
        'amount': amount,
        'type': 'expense',
        'category': f'🎯 {goal["name"]}',
        'date': datetime.now().isoformat(),
        'card': 'Накопление'
    }
    users[email]['transactions'].insert(0, transaction)
    
    save_users()
    
    return jsonify({
        'success': True,
        'balance': users[email]['balance'],
        'goal': goal,
        'transaction': transaction
    })

@app.route('/api/goals/<int:goal_id>', methods=['DELETE'])
@login_required
def delete_goal(goal_id):
    email = session['user_email']
    users[email]['goals'] = [g for g in users[email]['goals'] if g['id'] != goal_id]
    save_users()
    return jsonify({'success': True})

@app.route('/api/avatar', methods=['POST'])
@login_required
def update_avatar():
    email = session['user_email']
    
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename:
            ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'png'
            filename = f"{email}_{int(datetime.now().timestamp())}.{ext}"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            users[email]['avatar'] = f'/uploads/{filename}'
            save_users()
            return jsonify({'success': True, 'avatar': users[email]['avatar']})
    
    data = request.get_json()
    if data and 'avatar' in data:
        users[email]['avatar'] = data['avatar']
        save_users()
        return jsonify({'success': True, 'avatar': data['avatar']})
    
    return jsonify({'error': 'Неверные данные'}), 400

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
