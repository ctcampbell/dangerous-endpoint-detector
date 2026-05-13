"""
Extended example source code file to test the Dangerous Endpoint Detector

This file contains examples of all dangerous endpoint types including:
- Login endpoints
- Logout endpoints
- Password change endpoints
- Permission change endpoints
- Dangerous upsert/overwrite operations
"""

from flask import Flask, request, session, jsonify
from werkzeug.security import generate_password_hash

app = Flask(__name__)

# This should be detected as LOGIN
@app.post('/api/auth/login')
def login_user():
    """Authenticates a user and creates a session"""
    username = request.json.get('username')
    password = request.json.get('password')

    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
        session['user_id'] = user.id
        session['authenticated'] = True
        return jsonify({'message': 'Login successful', 'token': generate_token(user.id)})

    return jsonify({'error': 'Invalid credentials'}), 401

# This should be detected as LOGIN
@app.route('/api/signin', methods=['POST'])
def sign_in():
    """Alternative login endpoint"""
    email = request.json.get('email')
    password = request.json.get('password')

    user = authenticate(email, password)
    if user:
        create_session(user)
        return jsonify({'success': True})

    return jsonify({'error': 'Authentication failed'}), 401

# This should be detected as LOGOUT
@app.post('/api/auth/logout')
def logout_user():
    """Logs out the current user by clearing their session"""
    session.clear()
    return jsonify({'message': 'Successfully logged out'})

# This should be detected as PASSWORD CHANGE
@app.post('/api/users/<int:user_id>/password')
def change_password(user_id):
    """Changes a user's password"""
    data = request.get_json()
    new_password = data.get('new_password')

    user = User.query.get(user_id)
    if user:
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        return jsonify({'message': 'Password updated successfully'})

    return jsonify({'error': 'User not found'}), 404

# This should be detected as PERMISSION CHANGE
@app.post('/api/users/<int:user_id>/role')
def update_user_role(user_id):
    """Updates a user's role/permissions"""
    new_role = request.json.get('role')

    user = User.query.get(user_id)
    if user:
        user.role = new_role
        user.permissions = get_permissions_for_role(new_role)
        db.session.commit()
        return jsonify({'message': f'User role updated to {new_role}'})

    return jsonify({'error': 'User not found'}), 404

# This should be detected as DANGEROUS UPSERT/OVERWRITE
@app.put('/api/users/<int:user_id>')
def upsert_user(user_id):
    """
    DANGEROUS: This endpoint could accidentally overwrite existing user data
    including their password if the user already exists
    """
    data = request.get_json()

    # This is dangerous because it blindly updates ALL fields
    user = User.query.get(user_id)
    if not user:
        user = User(id=user_id)
        db.session.add(user)

    # Dangerous: overwrites all fields including password without validation
    user.username = data.get('username')
    user.email = data.get('email')
    user.password = data.get('password')  # Could accidentally overwrite!
    user.role = data.get('role')

    db.session.commit()
    return jsonify({'message': 'User upserted'})

# This should be detected as DANGEROUS UPSERT/OVERWRITE
@app.post('/api/users/create-or-update')
def create_or_update_user():
    """
    DANGEROUS: Upsert operation that could overwrite existing user passwords
    """
    data = request.json
    email = data.get('email')

    user = User.query.filter_by(email=email).first()
    if not user:
        user = User()
        db.session.add(user)

    # Dangerous merge without checking what's being overwritten
    for key, value in data.items():
        setattr(user, key, value)  # Could overwrite password!

    db.session.commit()
    return jsonify({'message': 'User saved'})

# This should be detected as DANGEROUS UPSERT/OVERWRITE
@app.put('/api/accounts/<account_id>')
def replace_account(account_id):
    """
    DANGEROUS: Complete replacement of account object without safeguards
    """
    new_account_data = request.json

    # Find or create pattern - dangerous!
    account = Account.query.get(account_id) or Account(id=account_id)

    # Blindly replace entire object including sensitive fields
    account.__dict__.update(new_account_data)

    db.session.commit()
    return jsonify({'status': 'updated'})

# This should NOT be detected (safe endpoint)
@app.get('/api/users/<int:user_id>/profile')
def get_user_profile(user_id):
    """Gets a user's profile - this is safe, just reading data"""
    user = User.query.get(user_id)
    if user:
        return jsonify({
            'id': user.id,
            'name': user.name,
            'email': user.email
        })
    return jsonify({'error': 'User not found'}), 404

# This should NOT be detected (safe endpoint with validation)
@app.patch('/api/users/<int:user_id>')
def update_user_safe(user_id):
    """
    SAFE: Partial update with field whitelisting
    """
    data = request.get_json()
    user = User.query.get(user_id)

    if not user:
        return jsonify({'error': 'User not found'}), 404

    # Safe: only allows specific, non-sensitive fields
    allowed_fields = ['name', 'bio', 'avatar_url']
    for field in allowed_fields:
        if field in data:
            setattr(user, field, data[field])

    db.session.commit()
    return jsonify({'message': 'User updated safely'})
