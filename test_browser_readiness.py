"""Actual Chrome: stalled images cannot make committed business HTML uncertain."""
import asyncio
import base64
import os
import pytest
import uvicorn
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, Response
from starlette.routing import Route
from browser import Browser
from app import ORIGIN
from tls_fixture import validate


@pytest.mark.asyncio
async def test_committed_dom_is_ready_while_visible_image_waits(request):
    if not request.config.getoption('--thread3-live-browser'):
        pytest.skip('BLOCKED: stalled-image browser check requires approved TLS and real Chrome')
    tls = validate(os.environ['THREAD3_TLS_DIR'])
    requested, release = asyncio.Event(), asyncio.Event()

    async def page(request):
        return HTMLResponse('<!doctype html><body data-page="catalog"><h1>Synthetic readiness fixture</h1>'
                            '<img width="16" height="16" src="/slow-image"></body>')

    async def slow_image(request):
        requested.set()
        await release.wait()
        return Response(base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'), media_type='image/gif')

    fixture = Starlette(routes=[Route('/shop', page), Route('/slow-image', slow_image)])
    server = uvicorn.Server(uvicorn.Config(fixture, host='127.0.0.1', port=8545,
        ssl_certfile=str(tls / 'cert.pem'), ssl_keyfile=str(tls / 'key.pem'),
        access_log=False, log_level='critical'))
    serving = asyncio.create_task(server.serve())
    browser = Browser(ORIGIN, [])
    try:
        for _ in range(100):
            if server.started:
                break
            if serving.done():
                await serving
            await asyncio.sleep(.05)
        assert server.started
        await browser.launch()
        snapshot = await asyncio.wait_for(browser.call('catalog'), 5)
        assert snapshot['page'] == 'catalog' and snapshot['url'] == ORIGIN + '/shop'
        await asyncio.wait_for(requested.wait(), 3)
        assert not release.is_set()
        screenshot = asyncio.create_task(browser.call('screenshot'))
        await asyncio.sleep(.1)
        assert not screenshot.done(), 'A screenshot must wait for the visible image'
        release.set()
        pixels = await asyncio.wait_for(screenshot, 5)
        assert base64.b64decode(pixels['data']).startswith(b'\x89PNG\r\n\x1a\n')
    finally:
        release.set()
        await browser.close()
        server.should_exit = True
        await asyncio.wait_for(serving, 10)
