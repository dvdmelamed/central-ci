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

    workflow_file = "ci.yml"
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
    return response


async def create_check_run(installation_access_token, gh, *args, **kwargs):
    owner = kwargs['owner']
    repo = kwargs['repo']
    check_name = kwargs['check_name']
    head_sha = kwargs['head_sha']
    status = kwargs['status']

    data = {
        'name': check_name,
        'head_sha': head_sha,
        'status': status,
    }

    url = f"/repos/{owner}/{repo}/check-runs"
    response = await gh.post(
        url,
        data=data,
        oauth_token=installation_access_token["token"]
    )
    return response["id"]


async def get_check_run(owner, repo, check_run_id, installation_access_token, gh):
    url = f"/repos/{owner}/{repo}/check-runs/{check_run_id}"
    response = await gh.getitem(
        url,
        oauth_token=installation_access_token["token"]
    )
    return response


async def update_check_run(owner, repo, check_run, status, conclusion, installation_access_token, gh):
    check_name = check_run['name']
    check_run_id = check_run['id']
    head_sha = check_run['head_sha']

    url = f"/repos/{owner}/{repo}/check-runs/{check_run_id}"
    response = await gh.patch(
        url,
        data={
            'name': check_name,
            'head_sha': head_sha,
            'status': status,
            'conclusion': conclusion
        },
        oauth_token=installation_access_token["token"]
    )
    return response


@routes.post("/check")
async def handle_create_check(request):
    try:
        body = await request.read()
        body = json.loads(body.decode('utf-8'))
        async with aiohttp.ClientSession() as session:
            gh = gh_aiohttp.GitHubAPI(session, "demo", cache=cache)
            await asyncio.sleep(1)
            owner = body.get('owner')
            repo = body.get('repo')
            check_name = body.get('check_name')
            installation_id = body.get('installation_id')
            head_sha = body.get('head_sha')
            installation_access_token = await get_installation_access_token(installation_id, gh)

            kwargs = dict(
                owner=owner,
                repo=repo,
                check_name=check_name,
                head_sha=head_sha,
                status='in_progress',
                installation_access_token=installation_access_token,
                gh=gh
            )

            check_run_id = await create_check_run(**kwargs)

        return web.Response(text=f"{check_run_id}")
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        return web.Response(status=500)


@routes.put("/check/{check_run_id}")
async def handle_update_check(request):
    try:
        body = await request.read()
        body = json.loads(body.decode('utf-8'))
        async with aiohttp.ClientSession() as session:
            gh = gh_aiohttp.GitHubAPI(session, "demo", cache=cache)
            await asyncio.sleep(1)
            installation_id = body.get('installation_id')
            owner = body.get('owner')
            repo = body.get('repo')
            conclusion = body.get('conclusion')  # failure
            check_run_id = request.match_info.get('check_run_id')
            installation_access_token = await get_installation_access_token(installation_id, gh)

            check_run = await get_check_run(
                owner=owner,
                repo=repo,
                check_run_id=check_run_id,
                installation_access_token=installation_access_token,
                gh=gh
            )

            check_run = await update_check_run(
                owner=owner,
                repo=repo,
                check_run=check_run,
                status="completed",
                conclusion=conclusion,
                installation_access_token=installation_access_token,
                gh=gh
            )

        return web.json_response(dict(check_run=check_run))
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        return web.Response(status=500)


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


@router.register("installation", action="created")
async def repo_installation_added(event, gh, *args, **kwargs):
    installation_id = event.data["installation"]["id"]

    installation_access_token = await apps.get_installation_access_token(
        gh,
        installation_id=installation_id,
        app_id=os.environ.get("GH_APP_ID"),
        private_key=os.environ.get("GH_PRIVATE_KEY")
    )

    repo_name = event.data["repositories"][0]["full_name"]
    url = f"/repos/{repo_name}/issues"
    response = await gh.post(
        url,
        data={'title': 'Thanks for installing my bot', 'body': 'Thanks!'},
        oauth_token=installation_access_token["token"]
    )
    return response


@router.register("check_suite", action="requested")
async def branch_created(event, gh, *args, **kwargs):
    print("Branch created")
    pass


@router.register("pull_request", action="opened")
async def pull_request_opened(event, gh, *args, **kwargs):
    return await handle_pr(event, gh, *args, **kwargs)


@router.register("pull_request", action="reopened")
async def pull_request_reopened(event, gh, *args, **kwargs):
    return await handle_pr(event, gh, *args, **kwargs)


def create_app(loop):
    app = web.Application()
    app.router.add_routes(routes)
    port = os.environ.get("PORT")
    if port is not None:
        port = int(port)
    return app


# if __name__ == "__main__":
#     app = web.Application()
#
#     app.router.add_routes(routes)
#     port = os.environ.get("PORT")
#     if port is not None:
#         port = int(port)
#     web.run_app(app, port=port)
