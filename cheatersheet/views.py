import logging
import re
from django.shortcuts import redirect
import requests
from urllib.parse import urljoin, urlparse

from django.conf import settings
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

CHEATERSHEET_WEB_SERVER_URL = getattr(settings, 'CHEATERSHEET_WEB_SERVER_URL', 'http://localhost:8072')
CHEATERSHEET_PROXY_WEB_URL = getattr(settings, 'CHEATERSHEET_PROXY_WEB_URL', '/cheatersheet/')

logger = logging.getLogger("radar.cheatersheet")
@method_decorator(csrf_exempt, name='dispatch')
class cheatersheet_proxy_web_view(View):
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs) -> HttpResponse:
        try:
            path = request.path.split(CHEATERSHEET_PROXY_WEB_URL.rstrip('/'))[1]
            path = path.lstrip('/')

            target_url = urljoin(CHEATERSHEET_WEB_SERVER_URL.rstrip('/') + '/', path)

            # Forward the request with the same method, data and headers
            if request.method == 'GET':
                response = requests.get(
                    target_url,
                    params=request.GET.dict(),
                    headers={k: v for k, v in request.headers.items() if k.lower() != 'host'},
                    cookies=request.COOKIES,
                    stream=True
                )
            elif request.method == 'POST':
                response = requests.post(
                    target_url,
                    data=request.body,
                    headers={k: v for k, v in request.headers.items() if k.lower() not in ['host', 'content-length']},
                    cookies=request.COOKIES,
                    stream=True
                )
            else:
                return HttpResponse(status=405)

            content_type = response.headers.get('Content-Type', '')

            if any(ct in content_type.lower() for ct in ['javascript', 'css', 'html']):
                content = response.content.decode('utf-8')

                # Extract base URL from target
                parsed_target = urlparse(CHEATERSHEET_WEB_SERVER_URL)
                base_url = f"{parsed_target.scheme}://{parsed_target.netloc}"

                content = content.replace(f'"{base_url}/', f'"{CHEATERSHEET_PROXY_WEB_URL}')
                content = content.replace(f"'{base_url}/", f"'{CHEATERSHEET_PROXY_WEB_URL}")

                proxy_base = CHEATERSHEET_PROXY_WEB_URL.rstrip('/')

                # Special handling for fetch API calls in JavaScript files
                if 'javascript' in content_type.lower():
                    # Handle fetch('/endpoint') pattern
                    content = re.sub(r'fetch\s*\(\s*[\'"](\/)([^\'")]+)[\'"]',
                                    fr'fetch("{proxy_base}/\2"', 
                                    content)

                    # Handle fetch with template literals - fetch(`/endpoint`)
                    content = re.sub(r'fetch\s*\(\s*`(\/)([^`]+)`',
                                    fr'fetch(`{proxy_base}/\2`',
                                    content)

                    # Handle fetch with variable URLs but path starting with /
                    content = re.sub(r'fetch\s*\(\s*(\w+\s*\+\s*)[\'"](\/)([^\'")]+)[\'"]',
                                    fr'fetch(\1"{proxy_base}/\3"',
                                    content)

                content = re.sub(r'(["\']\s*)(/)(?!{})'.format(proxy_base.lstrip('/')),
                                r'\1{}/'.format(proxy_base),
                                content)

                return HttpResponse(content, content_type=content_type, status=response.status_code)


            streaming_response = StreamingHttpResponse(
                response.iter_content(chunk_size=8192),
                status=response.status_code,
                content_type=content_type
            )

            for header, value in response.headers.items():
                if header.lower() not in ['content-encoding', 'transfer-encoding', 'content-length']:
                    streaming_response[header] = value

            return streaming_response

        except Exception as e:
            return HttpResponse(f"Error proxying request: {e}", status=500)


@login_required
def cheatersheet_api_add_comparison(request, submission_id):
    """
    Proxy for adding a flag for a particular submission to the cheatersheet API.
    """
    try:
        token = settings.CHEATERSHEET_API_TOKEN

        print(f"Adding flag for submission {submission_id} with token {token}")

        target_url = (CHEATERSHEET_WEB_SERVER_URL + '/api/submissions/' + submission_id + '/')

        print(f"Target URL: {target_url}")

        headers = {
            'Authorization': f'Token {token}',
            'Content-Type': 'application/json'
        }

        student_key = request.POST.get('student_key')
        course_key = request.POST.get('course_key')
        submission_key = request.POST.get('submission_id')

        data = {
            "flagged": True,
            "student_key": student_key,
            "other_student_key": request.POST.get('other_student_key'),
            "course_key": course_key,
            "submission_key": submission_key,
            "other_submission_key": request.POST.get('other_submission_id'),
            "similarity": request.POST.get('similarity'),
            "comparison": "true"
        }

        print(f"Sending data: {data}")

        # Flag a submission
        response = requests.post(
            target_url,
            json=request.POST,
            headers=headers
        )

        return JsonResponse(response.json(), status=response.status_code)

    except Exception as e:
        return HttpResponse(f"Error adding flag: {e}", status=500)


def go_to_cheatersheet_view(request, report_id):
    return redirect(f"{CHEATERSHEET_PROXY_WEB_URL.rstrip('/')}/#/report/{report_id}")