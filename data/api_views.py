from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse
import requests

from django.conf import settings

# Cheatersheet API proxy views
@api_view(['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@permission_classes([IsAuthenticated])
def cheatersheet_api_proxy(request, path=''):
    """
    Proxy API calls to cheatersheet service
    """
    try:
        # Get cheatersheet server URL from settings
        cheatersheet_url = getattr(settings, 'CHEATERSHEET_WEB_SERVER_URL', 'http://localhost:8072')
        token = getattr(settings, 'CHEATERSHEET_API_TOKEN', '')

        # Construct the target URL
        target_url = f"{cheatersheet_url.rstrip('/')}/api/{path.lstrip('/')}"

        # Prepare headers
        headers = {
            'Authorization': f'Token {token}',
            'Content-Type': 'application/json'
        }

        # Forward the request
        if request.method == 'GET':
            response = requests.get(
                target_url,
                params=request.GET.dict(),
                headers=headers
            )
        elif request.method == 'POST':
            response = requests.post(
                target_url,
                json=request.data,
                headers=headers
            )
        elif request.method == 'PUT':
            response = requests.put(
                target_url,
                json=request.data,
                headers=headers
            )
        elif request.method == 'PATCH':
            response = requests.patch(
                target_url,
                json=request.data,
                headers=headers
            )
        elif request.method == 'DELETE':
            response = requests.delete(
                target_url,
                headers=headers
            )
        else:
            return Response({'error': 'Method not allowed'}, status=405)

        # Return the response from cheatersheet
        try:
            return Response(response.json(), status=response.status_code)
        except ValueError:
            # Response is not JSON
            return HttpResponse(
                response.content,
                content_type=response.headers.get('Content-Type', 'text/plain'),
                status=response.status_code
            )

    except Exception as e:
        return Response({'error': str(e)}, status=500)
