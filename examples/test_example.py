"""
Example source code file to test the Dangerous Endpoint Detector

This file contains several endpoints that should be flagged as dangerous.
Copy and paste this into the UI to test the tool.
"""

from flask import Flask, request, session, jsonify
from werkzeug.security import generate_password_hash

app = Flask(__name__)

# This should be detected as LOGOUT
@app.post('/api/auth/logout')
def logout_user():
    """Logs out the current user by clearing their session"""
    session.clear()
    return jsonify({'message': 'Successfully logged out'})

# This should be detected as LOGOUT
@app.route('/api/signout', methods=['POST'])
def sign_out():
    """Alternative logout endpoint"""
    user_id = session.get('user_id')
    if user_id:
        # Revoke all tokens for this user
        revoke_user_tokens(user_id)
        session.pop('user_id', None)
    return jsonify({'status': 'signed out'})

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

# This should be detected as PASSWORD CHANGE
@app.route('/api/reset-password', methods=['PUT'])
def reset_password():
    """Resets a user's password"""
    email = request.json.get('email')
    user = User.query.filter_by(email=email).first()

    if user:
        # Generate temporary password
        temp_password = generate_temp_password()
        user.password = hash_password(temp_password)
        db.session.commit()
        send_email(email, temp_password)

    return jsonify({'message': 'If email exists, password reset sent'})

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

# This should be detected as PERMISSION CHANGE
@app.route('/api/admin/grant-access', methods=['POST'])
def grant_admin_access():
    """Grants admin access to a user"""
    user_id = request.json.get('user_id')

    user = User.query.get(user_id)
    user.is_admin = True
    user.permissions.append('admin')
    db.session.commit()

    return jsonify({'message': 'Admin access granted'})

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

# This should NOT be detected (safe endpoint)
@app.post('/api/posts')
def create_post():
    """Creates a new post - this is safe"""
    title = request.json.get('title')
    content = request.json.get('content')

    post = Post(title=title, content=content)
    db.session.add(post)
    db.session.commit()

    return jsonify({'message': 'Post created', 'id': post.id}), 201
