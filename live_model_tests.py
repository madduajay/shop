"""Opt-in test-process request guard. Never loads or persists a credential."""
import json
import threading


class ModelBudget:
    def __init__(self, requests, model, output_tokens=1200, input_bytes=131072, max_requests=50):
        if type(requests) is not int or not 1 <= requests <= max_requests:
            raise ValueError(f'Live-model request cap must be between 1 and {max_requests}')
        self.limit = requests
        self.model = model
        self.output_tokens = output_tokens
        self.input_bytes = input_bytes
        self.used = 0
        self._lock = threading.Lock()

    def claim(self, request):
        url = request.url
        if (request.method != 'POST' or url.scheme != 'https' or
                url.host != 'api.openai.com' or url.port not in (None, 443) or
                url.path not in ('/v1/responses', '/v1/chat/completions') or
                url.query or url.username or url.password):
            raise RuntimeError('Live-model request outside approved OpenAI HTTPS endpoints')
        if len(request.content) > self.input_bytes:
            raise RuntimeError('Live-model input byte cap exceeded')
        body = json.loads(request.content)
        tokens = body.get('max_output_tokens', body.get('max_completion_tokens', body.get('max_tokens')))
        if (body.get('model') != self.model or body.get('store') is not False or
                type(tokens) is not int or not 1 <= tokens <= self.output_tokens or
                body.get('stream') or body.get('n', 1) != 1):
            raise RuntimeError('Live-model model, retention or output limits rejected')
        with self._lock:
            if self.used >= self.limit:
                raise RuntimeError('Live-model session request budget exhausted')
            # Failed requests consume budget too; retries never receive free claims.
            self.used += 1
