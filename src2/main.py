import asyncio
import os
import sys
import json
import base64
import traceback

import aiohttp
from aiohttp import web
import cachetools
from gidgethub import aiohttp as gh_aiohttp
from gidgethub import routing
from gidgethub import sansio
from gidgethub import apps

router = routing.Router()
cache = cachetools.LRUCache(maxsize=500)

routes = web.RouteTableDef()


async def get_installation_access_token(installation_id, gh, *args, **kwargs):
    installation_access_token = await apps.get_installation_access_token(
        gh,
        installation_id=installation_id,
        app_id=os.environ.get("GH_APP_ID"),
        private_key=f"{base64.b64decode(os.environ.get('GH_PRIVATE_KEY')).decode('utf-8')}"
    )
    return installation_access_token


async def handle_pr(event, gh, *args, **kwargs):

    installation_id = event.data["installation"]["id"]
    installation_access_token = await get_installation_access_token(installation_id, gh, *args, **kwargs)

    client_payload = {
        'owner': event.data["pull_request"]["head"]["user"]["login"],
        'repo': event.data["pull_request"]["head"]['repo']['name'],
        'full_repo_path': event.data["pull_request"]["head"]['repo']['full_name'],
        'head_sha': event.data["pull_request"]["head"]["sha"],
        'installation_id': installation_id,
        'github_token': installation_access_token["token"]
    }

    workflow_file = "ci0.yml"
    url = f"/repos/centralized-ci/ci/actions/workflows/{workflow_file}/dispatches"
    response = await gh.post(
        url,
        data={
            'ref': 'main',
            'inputs': {
                'client_payload': json.dumps(client_payload)
            }
        },
        oauth_token=installation_access_token["token"]
    )
    print(response)
    return response


@routes.post("/webhook")
async def webhook(request):
    try:
        body = await request.read()
        secret = os.environ.get("GH_SECRET")
        event = sansio.Event.from_http(request.headers, body, secret=secret)
        if event.event == "ping":
            return web.Response(status=200)
        async with aiohttp.ClientSession() as session:
            gh = gh_aiohttp.GitHubAPI(session, "demo", cache=cache)
            await asyncio.sleep(1)
            await router.dispatch(event, gh)
        try:
            print("GH requests remaining:", gh.rate_limit.remaining)
        except AttributeError:
            pass
        return web.Response(status=200)
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        return web.Response(status=500)


@router.register("pull_request", action="opened")
async def pull_request_opened(event, gh, *args, **kwargs):
    return await handle_pr(event, gh, *args, **kwargs)


@router.register("pull_request", action="reopened")
async def pull_request_reopened(event, gh, *args, **kwargs):
    return await handle_pr(event, gh, *args, **kwargs)


def create_app(loop):
    app = web.Application()
    app.router.add_routes(routes)
    return app
