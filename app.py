# Actually some inspiration and some things took from those examples:
# https://github.com/Stonebound/patreon-to-discord-webhooks/blob/master/index.php
# https://github.com/Commit451/skyhook/blob/master/src/provider/Patreon.ts

from pydantic import BaseModel
from fastapi import FastAPI, Header
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

from datetime import datetime
from discord import Webhook, AsyncWebhookAdapter

import json
import discord
import aiohttp


app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)


with open("config.json") as data:
    config = json.load(data)


class PatreonPayload(BaseModel):
    data: dict
    included: list


async def post_to_discord(url: str, **kwargs: dict):
    async with aiohttp.ClientSession() as session:
        webhook = Webhook.from_url(url, adapter=AsyncWebhookAdapter(session))
        await webhook.send(**kwargs)


def get_type_event(request: Request):
    return request.headers.get("x-patreon-event")


@app.post("/webhook")
async def patreon(request: Request, payload: PatreonPayload = None):
    if request.headers.get("x-patreon-signature") != config["patreon_secret"]:
        return JSONResponse(
            content=dict(success=False, message="Wrong Patreon signature."), status_code=403
        )
    if not payload:
        return JSONResponse(
            content=dict(success=False, message="Payload data missed."), status_code=400
        )

    em = discord.Embed(color=0xF96854, timestamp=datetime.now())
    event = get_type_event(request)
    data = payload.data
    for included_data in payload.included:
        if (
            included_data["type"] == "user"
            and included_data["id"] == data["relationships"]["patron"]["data"]["id"]
        ):
            em.set_author(
                name=included_data["attributes"]["full_name"],
                url=included_data["attributes"]["url"],
                icon_url=included_data["attributes"]["thumb_url"],
            )
        elif (
            included_data["type"] == "campaign"
            and included_data["id"] == data["relationships"]["campaign"]["data"]["id"]
        ):
            campaign_sum = included_data["attributes"]["pledge_sum"]
            patron_count = included_data["attributes"]["patron_count"]
        elif (
            included_data["type"] == "reward"
            and included_data["id"] == data["relationships"]["reward"]["data"]["id"]
        ):
            reward_data = included_data

    description = {
        "pledges:create": "Unlocked",
        "pledges:update": "Updated",
        "pledges:delete": "Lost",
    }
    em.description = (
        f"{description[event]}: [**{reward_data['attributes']['title']} - "
        f"${reward_data['attributes']['amount_cents'] / 100:.2f} per month**]({reward_data['attributes']['url']}).\n"
        f"New total: **${campaign_sum / 100:.2f} by {patron_count:,} Patrons**."
    )
    await post_to_discord(
        url=config["discord_webhook_url"],
        username="Patreon",
        avatar_url="https://upload.wikimedia.org/wikipedia/commons/thumb/5/5a/Patreon_logomark.svg/1200px-Patreon_logomark.svg.png",
        embed=em,
    )

    return JSONResponse(content=dict(success=True))
