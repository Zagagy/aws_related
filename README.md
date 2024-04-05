# AWS Related Apps
Overview
This repository contains the following applications:

1. User Applications Management App: A Flask-based application for managing user permissions and applications through a REST API. It supports operations such as validating user credentials, updating user applications lists, and managing applications within the system. This app utilizes AWS DynamoDB for storing user data and AWS S3 for maintaining the list of available applications.

2. Image Subject Line Generator App: An application leveraging AWS Claude Bedrock's image processing and AI capabilities to generate subject lines for images. This app demonstrates integrating AWS's AI services to extract meaningful context from images and generate descriptive subject lines.

## Getting Started
Prerequisites:
* Python 3.8+
* Flask
* Boto3
* AWS CLI (configured with access to DynamoDB and S3)
