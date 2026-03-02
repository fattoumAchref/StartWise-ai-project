import os

from django.http import HttpResponse


class SimpleCORSMiddleware:
    """
    Minimal CORS middleware to support local Next.js frontend calls.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.allow_origin = os.getenv("CORS_ALLOW_ORIGIN", "http://localhost:3000")
        self.allow_headers = os.getenv(
            "CORS_ALLOW_HEADERS",
            "Content-Type, Authorization, X-Requested-With",
        )
        self.allow_methods = os.getenv(
            "CORS_ALLOW_METHODS",
            "GET, POST, DELETE, OPTIONS",
        )

    def __call__(self, request):
        if request.method == "OPTIONS":
            response = HttpResponse(status=204)
            return self._add_headers(response)

        response = self.get_response(request)
        return self._add_headers(response)

    def _add_headers(self, response):
        response["Access-Control-Allow-Origin"] = self.allow_origin
        response["Access-Control-Allow-Headers"] = self.allow_headers
        response["Access-Control-Allow-Methods"] = self.allow_methods
        return response
