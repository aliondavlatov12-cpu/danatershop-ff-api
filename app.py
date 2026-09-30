import os
import time
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

API_KEY = os.getenv("API_KEY", "").strip()

# Cache:
# uid -> {"data": ..., "expires": ...}
CACHE = {}

CACHE_SECONDS = 300
TIMEOUT = 8

# Free Fire data sources.
# Мо якчанд source истифода мебарем.
SOURCES = [
    "https://free-ff-api-src-5plp.onrender.com/api/v1/account",
]


def valid_uid(uid):
    return uid.isdigit() and 5 <= len(uid) <= 20


def get_cached(uid, region):
    key = f"{uid}:{region}"

    item = CACHE.get(key)

    if not item:
        return None

    if item["expires"] < time.time():
        CACHE.pop(key, None)
        return None

    return item["data"]


def save_cache(uid, region, data):
    key = f"{uid}:{region}"

    CACHE[key] = {
        "data": data,
        "expires": time.time() + CACHE_SECONDS
    }


def normalize_response(raw, uid, region):
    """
    Convert different Free Fire API response formats
    into our own stable format.
    """

    basic = (
        raw.get("basicInfo")
        or raw.get("basicinfo")
        or raw.get("AccountInfo")
        or raw.get("accountInfo")
        or {}
    )

    nickname = (
        basic.get("nickname")
        or basic.get("nickName")
        or basic.get("AccountName")
        or basic.get("accountName")
    )

    level = (
        basic.get("level")
        or basic.get("Level")
        or basic.get("AccountLevel")
    )

    real_region = (
        basic.get("region")
        or basic.get("Region")
        or basic.get("AccountRegion")
        or region
    )

    account_id = (
        basic.get("accountId")
        or basic.get("accountid")
        or basic.get("AccountID")
        or uid
    )

    if not nickname:
        return None

    return {
        "success": True,
        "uid": str(account_id),
        "nickname": str(nickname),
        "level": level,
        "region": str(real_region),
    }


def lookup_player(uid, region):
    for url in SOURCES:
        try:
            response = requests.get(
                url,
                params={
                    "region": region,
                    "uid": uid
                },
                timeout=TIMEOUT
            )

            if response.status_code != 200:
                continue

            raw = response.json()

            result = normalize_response(raw, uid, region)

            if result:
                return result

        except Exception:
            continue

    return None


@app.route("/")
def home():
    return jsonify({
        "service": "DanaterShop Free Fire API",
        "status": "online",
        "version": "1.0.0"
    })


@app.route("/health")
def health():
    return jsonify({
        "status": "ok"
    })


@app.route("/api/player")
def player():
    # Optional API key protection
    if API_KEY:
        supplied_key = request.headers.get("X-API-Key", "")

        if supplied_key != API_KEY:
            return jsonify({
                "success": False,
                "error": "invalid_api_key"
            }), 401

    uid = request.args.get("uid", "").strip()
    region = request.args.get("region", "CIS").strip().upper()

    if not valid_uid(uid):
        return jsonify({
            "success": False,
            "error": "invalid_uid",
            "message": "UID must contain 5-20 digits."
        }), 400

    cached = get_cached(uid, region)

    if cached:
        return jsonify(cached)

    result = lookup_player(uid, region)

    if not result:
        return jsonify({
            "success": False,
            "error": "player_not_found_or_source_unavailable",
            "uid": uid,
            "region": region
        }), 404

    save_cache(uid, region, result)

    return jsonify(result)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))

    app.run(
        host="0.0.0.0",
        port=port
  )
