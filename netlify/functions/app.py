import os
import json
import base64
from urllib.parse import parse_qs

# Import the Flask app
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from simple_app_serverless import app as flask_app

def handler(event, context):
    """Serverless function handler to proxy requests to Flask app"""
    
    # Parse request from Netlify
    path = event.get('path', '/')
    http_method = event['httpMethod']
    headers = event.get('headers', {})
    
    # Handle query string parameters
    query_string_parameters = event.get('queryStringParameters', {}) or {}
    multivalue_query_string_parameters = event.get('multiValueQueryStringParameters', {}) or {}
    
    # Handle body
    body = event.get('body', '')
    if body and event.get('isBase64Encoded', False):
        body = base64.b64decode(body)
    
    # Create WSGI environment
    environ = {
        'REQUEST_METHOD': http_method,
        'PATH_INFO': path,
        'QUERY_STRING': '&'.join([f"{k}={v}" for k, v in query_string_parameters.items()]),
        'CONTENT_LENGTH': str(len(body) if body else ''),
        'SERVER_NAME': headers.get('host', 'localhost'),
        'SERVER_PORT': '443',
        'SERVER_PROTOCOL': 'HTTP/1.1',
        'wsgi.version': (1, 0),
        'wsgi.url_scheme': 'https',
        'wsgi.input': body,
        'wsgi.errors': sys.stderr,
        'wsgi.multithread': False,
        'wsgi.multiprocess': False,
        'wsgi.run_once': False,
    }
    
    # Add HTTP headers
    for key, value in headers.items():
        key = key.upper().replace('-', '_')
        if key not in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
            key = f'HTTP_{key}'
        environ[key] = value
    
    # Response data
    response_data = {
        'statusCode': 200,
        'headers': {},
        'body': '',
        'isBase64Encoded': False,
    }
    
    def start_response(status, response_headers, exc_info=None):
        status_code = int(status.split()[0])
        response_data['statusCode'] = status_code
        
        for header, value in response_headers:
            response_data['headers'][header] = value
    
    # Run the Flask app
    response_body = b''
    for data in flask_app(environ, start_response):
        if isinstance(data, str):
            response_body += data.encode('utf-8')
        else:
            response_body += data
    
    # Check if the response should be Base64 encoded
    content_type = response_data['headers'].get('Content-Type', '')
    is_binary = not content_type.startswith(('text/', 'application/json'))
    
    if is_binary:
        response_data['body'] = base64.b64encode(response_body).decode('utf-8')
        response_data['isBase64Encoded'] = True
    else:
        response_data['body'] = response_body.decode('utf-8')
    
    return response_data 