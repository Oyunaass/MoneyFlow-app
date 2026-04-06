from flask import Flask, render_template, request, jsonify, session, send_from_directory
from functools import wraps
import hashlib
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

users = {}


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return jsonify({'error': 'Не авторизован'}), 401
        return f(*args, **kwargs)

    return decorated_function


def add_demo_transactions(user_email):
    now = datetime.now()
    transactions = [
        {'id': int((now - timedelta(days=5)).timestamp() * 1000), 'amount': 1500, 'type': 'expense',
         'category': 'Транспорт', 'date': (now - timedelta(days=5)).isoformat(), 'card': 'Основной'},
        {'id': int((now - timedelta(days=4)).timestamp() * 1000), 'amount': 17500, 'type': 'expense',
         'category': 'Жилье', 'date': (now - timedelta(days=4)).isoformat(), 'card': 'Основной'},
        {'id': int((now - timedelta(days=3)).timestamp() * 1000), 'amount': 15000, 'type': 'expense',
         'category': 'Продукты', 'date': (now - timedelta(days=3)).isoformat(), 'card': 'Основной'},
        {'id': int((now - timedelta(days=2)).timestamp() * 1000), 'amount': 5000, 'type': 'expense',
         'category': 'Здоровье', 'date': (now - timedelta(days=2)).isoformat(), 'card': 'Основной'},
        {'id': int((now - timedelta(days=1)).timestamp() * 1000), 'amount': 15000, 'type': 'expense',
         'category': 'Одежда', 'date': (now - timedelta(days=1)).isoformat(), 'card': 'Основной'},
        {'id': int(now.timestamp() * 1000), 'amount': 100000, 'type': 'income', 'category': 'Зарплата',
         'date': now.isoformat(), 'card': 'Основной'}
    ]
    users[user_email]['transactions'] = transactions
    users[user_email]['balance'] = sum(t['amount'] if t['type'] == 'income' else -t['amount'] for t in transactions)
    users[user_email]['goals'] = []


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

    add_demo_transactions(email)

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
    return jsonify({'success': True})


@app.route('/api/avatar', methods=['POST'])
@login_required
def update_avatar():
    email = session['user_email']
    data = request.get_json()

    if 'avatar' in data:
        users[email]['avatar'] = data['avatar']
        return jsonify({'success': True, 'avatar': data['avatar']})

    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename:
            filename = f"{email}_{int(datetime.now().timestamp())}.png"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            users[email]['avatar'] = f'/uploads/{filename}'
            return jsonify({'success': True, 'avatar': users[email]['avatar']})

    return jsonify({'error': 'Неверные данные'}), 400


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


if __name__ == '__main__':
    app.run(debug=True, port=5000)