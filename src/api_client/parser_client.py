from typing import Any, Dict, List, Optional

import httpx

from src.config import Config


class ParserApiError(Exception):
    def __init__(self, code: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class ParserClient:
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = (base_url or Config.PARSER_API_URL).rstrip('/')
        self.api_key = api_key if api_key is not None else Config.PARSER_API_KEY
        headers = {'Accept': 'application/json'}
        if self.api_key:
            headers['X-API-Key'] = self.api_key
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=httpx.Timeout(180.0, connect=10.0),
        )

    async def close(self):
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        response = await self._client.request(method, path, **kwargs)

        try:
            payload = response.json()
        except Exception:
            raise ParserApiError(
                'INVALID_RESPONSE',
                f'Non-JSON response from parser API (status {response.status_code})',
            )

        if not payload.get('ok'):
            error = payload.get('error', {})
            raise ParserApiError(
                error.get('code', 'UNKNOWN'),
                error.get('message', 'Unknown error'),
                error.get('details'),
            )

        return payload['data']

    async def health(self) -> Dict[str, Any]:
        return await self._request('GET', '/api/v1/health')

    async def list_sources(self) -> List[Dict[str, Any]]:
        data = await self._request('GET', '/api/v1/sources')
        return data['items']

    async def parse_inn(self, inn: str, sources: Optional[List[str]] = None) -> Dict[str, Any]:
        body = {'inn': inn}
        if sources:
            body['sources'] = sources
        return await self._request('POST', '/api/v1/parses', json=body)

    async def get_latest(self, inn: str) -> Dict[str, Any]:
        return await self._request('GET', f'/api/v1/companies/{inn}/latest')

    async def get_diff_latest(self, inn: str) -> Dict[str, Any]:
        return await self._request('GET', f'/api/v1/companies/{inn}/diff/latest')

    async def get_history(self, inn: str, limit: int = 20) -> Dict[str, Any]:
        return await self._request(
            'GET', f'/api/v1/companies/{inn}/history',
            params={'limit': limit},
        )