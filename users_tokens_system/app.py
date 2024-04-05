import json
import random
import string
from flask import Flask, request, jsonify
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import boto3
import os

app = Flask(__name__)

# DynamoDB setup
dynamodb = boto3.resource('dynamodb')
users_table = dynamodb.Table('Users')

# Slack setup
slack_client = WebClient(token=os.getenv('SLACK_BOT_TOKEN'))

# bucket related consts:
apps_bucket = 'your-bucket-name'
apps_path_in_s3 = 'allowed_applications.json'

ADMIN_APP = 'admin_app'


def get_allowed_applications_from_s3():
    """
    Fetches the list of allowed applications from a JSON file stored in S3.
    """
    s3 = boto3.client('s3')
    response = s3.get_object(Bucket=apps_bucket, Key=apps_path_in_s3)
    content = response['Body'].read().decode('utf-8')
    allowed_applications = json.loads(content)
    return allowed_applications.get('applications', [])


applications = get_allowed_applications_from_s3()


def save_applications_to_s3(applications):
    """
    Saves the updated list of applications to a JSON file in S3.
    """
    s3 = boto3.client('s3')
    s3.put_object(Bucket=apps_bucket, Key=apps_path_in_s3, Body=json.dumps(applications).encode('utf-8'))


def validate_user_and_token(username, token, application=None):
    try:
        response = users_table.get_item(Key={'username': username})
    except Exception as e:
        return False, f"Error retrieving user from database: {e}"

    if 'Item' not in response:
        return False, "User not found."

    user = response['Item']

    # Check if the token matches
    if token != user.get('token'):
        return False, "Invalid token."

    # Check if the user has access to the app:
    if application and application not in user.get('applications', []):
        return False, f'User does not have access to the application {application}.'

    return True, ''


def generate_random_token(length=50):
    # Generate a random 50-character token.
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for i in range(length))


def send_direct_message_to_slack(user_slack_id, message):
    # Send a direct message to a user's Slack ID.
    try:
        response = slack_client.chat_postMessage(channel=user_slack_id, text=message)
        return response
    except SlackApiError as e:
        print(e.response['error'])
        return None


@app.route('/generate_token', methods=['POST'])
def generate_token():
    username = request.args.get('user')
    if not username:
        return jsonify({"error": 'Username is required'}), 400

    # Check if the user exists and retrieve the user's Slack ID
    try:
        response = users_table.get_item(Key={'username': username})
        user_item = response.get('Item')
        if not user_item:
            return jsonify({"error": 'User not found'}), 404
        user_slack_id = user_item.get('slack_id')
        if not user_slack_id:
            return jsonify({"error": 'User Slack ID not found'}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Generate a random 50-character token
    token = generate_random_token()

    # Update the user item in DynamoDB with the new token
    users_table.update_item(
        Key={'username': username},
        UpdateExpression='SET token = :val',
        ExpressionAttributeValues={
            ':val': token
        },
    )

    # Send the token as a direct message to the user's Slack ID
    slack_message = f'Your new token: {token}'
    send_direct_message_to_slack(user_slack_id, slack_message)

    return jsonify({"message": f'Token generated for user {username} and sent via Slack DM.'})


@app.route('/add_user', methods=['POST'])
def add_user():
    admin_username = request.json.get('admin_user')
    token = request.json.get('token')
    new_username = request.json.get('new_user')
    new_user_slack_id = request.json.get('slack_id')

    # Validate admin user and token
    is_valid, message = validate_user_and_token(admin_username, token, ADMIN_APP)
    if not is_valid:
        return jsonify({"error": message or 'Invalid admin credentials'}), 403

    # Proceed to add the new user and their Slack ID to the DynamoDB table
    try:
        users_table.put_item(
            Item={
                'username': new_username,  # Primary key
                'slack_id': new_user_slack_id
            }
        )
        return jsonify({"message": f'User {new_username} added successfully'}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/validateUser', methods=['POST'])
def validate_user():
    data = request.json
    username = data.get('username')
    token = data.get('token')
    application = data.get('application')

    if not username or not token:
        return jsonify({"error": 'Username and token are required'}), 400

    # Validate user and token without checking for admin status
    is_valid, message, = validate_user_and_token(username, token, application)

    if not is_valid:
        return jsonify({"error": message or 'Invalid credentials'}), 403

    return jsonify({"message": 'User and token validated successfully'})


@app.route('/deleteUser', methods=['DELETE'])
def delete_user():
    admin_username = request.json.get('admin_username')
    admin_token = request.json.get('admin_token')
    username_to_delete = request.json.get('username_to_delete')

    # First, verify the requester is an admin and check his token
    is_valid, message = validate_user_and_token(admin_username, admin_token, ADMIN_APP)
    if not is_valid:
        return jsonify({"error": 'Unauthorized or invalid credentials'}), 403

    # Proceed to delete the user
    try:
        response = users_table.delete_item(
            Key={
                'username': username_to_delete
            }
        )
        print(str(response))
        return jsonify({"message": f'User {username_to_delete} successfully deleted'}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/updateUserApplications', methods=['PUT'])
def update_user_applications():
    # Update a user's applications list (admin only)
    admin_username = request.json.get('admin_username')
    admin_token = request.json.get('admin_token')
    user_username = request.json.get('user_username')
    new_applications = request.json.get('new_applications')

    # Validate admin credentials
    is_valid, message = validate_user_and_token(admin_username, admin_token, ADMIN_APP)
    if not is_valid:
        return jsonify({"error": 'Unauthorized or invalid credentials {message}'}), 403

    # Check all new applications exist in the allowed applications list
    if not all(app in applications for app in new_applications):
        return jsonify({"error": 'One or more applications are not allowed'}), 400

    # Update user's applications list in DynamoDB
    try:
        response = users_table.update_item(
            Key={'username': user_username},
            UpdateExpression='SET applications = :val',
            ExpressionAttributeValues={
                ':val': new_applications
            },
            ReturnValues='UPDATED_NEW'
        )
        print(response)
        return jsonify({"message": f'Applications updated successfully for user {user_username}'}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/getApplications', methods=['POST'])
def get_applications():
    admin_username = request.json.get('admin_username')
    admin_token = request.json.get('admin_token')

    is_valid, message = validate_user_and_token(admin_username, admin_token, ADMIN_APP)
    if not is_valid:
        return jsonify({"error": 'Unauthorized or invalid credentials: {message}'}), 403
    global applications
    return jsonify(applications)


@app.route('/addApplication', methods=['POST'])
def add_application():
    admin_username = request.json.get('admin_username')
    admin_token = request.json.get('admin_token')
    new_application = request.json.get('application')

    is_valid, message = validate_user_and_token(admin_username, admin_token, ADMIN_APP)
    if not is_valid:
        return jsonify({"error": 'Unauthorized or invalid credentials: {message}'}), 403

    global applications
    if new_application in applications:
        return jsonify({"message": 'application already exists'}), 409
    applications.append(new_application)
    save_applications_to_s3(applications)
    return jsonify({"message": f'Application {new_application} added successfully'})


@app.route('/deleteApplication', methods=['POST'])
def delete_application():
    admin_username = request.json.get('admin_username')
    admin_token = request.json.get('admin_token')
    application_to_delete = request.json.get('application')

    is_valid, message = validate_user_and_token(admin_username, admin_token, ADMIN_APP)
    if not is_valid:
        return jsonify({"error": 'Unauthorized or invalid credentials: {message}'}), 403

    global applications
    if application_to_delete not in applications:
        return jsonify({"message": 'Application does not exist'}), 404
    applications.remove(application_to_delete)
    save_applications_to_s3(applications)
    return jsonify({"message": f'Application {application_to_delete} deleted successfully'})


if __name__ == '__main__':
    app.run(debug=True)
