from flask import Flask, request, jsonify
import asyncio
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii
import aiohttp
import requests
import json
import like_pb2
import uid_generator_pb2
import visit_count_pb2
from google.protobuf.message import DecodeError
from collections import OrderedDict
import hmac
import os
import threading
import secrets
import time

app = Flask(__name__)

# ================= PRIVATE KEY SYSTEM =================
KEYS_FILE = os.getenv("KEYS_FILE", "keys.json")      # key data store
ADMIN_KEY = os.getenv("ADMIN_KEY", "@slowgoods")  # only owner knows this
OWNER = "@ISHRAKSHADMAN"   # সব response এ আসবে
DEFAULT_LIMIT = 120        # default limit per key
COUNT_MIN_LIKES = 99      # like_given >= 99 hole-i usage count hobe, tar niche hole count hobe na
LIMIT_MSG = "API limit ended. Contact owner for renew."
_lock = threading.Lock()


def load_keys():
    try:
        with open(KEYS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as e:
        app.logger.error(f"Error loading keys: {e}")
        return {}


def save_keys(data):
    tmp = KEYS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, KEYS_FILE)


def admin_ok(provided):
    return provided is not None and hmac.compare_digest(str(provided), ADMIN_KEY)


def find_key(provided):
    """Return (key, info) if exists, else (None, None)."""
    if not provided:
        return None, None
    keys = load_keys()
    for k, info in keys.items():
        if hmac.compare_digest(str(provided), k):
            return k, info
    return None, None


@app.after_request
def add_owner(resp):
    """সব JSON response এ owner যোগ করে (success, error, limit end, renew সব)।"""
    try:
        if resp.mimetype == "application/json":
            data = json.loads(resp.get_data(as_text=True), object_pairs_hook=OrderedDict)
            if isinstance(data, dict):
                data["owner"] = OWNER
                resp.set_data(json.dumps(data, separators=(',', ':'), ensure_ascii=False))
    except Exception as e:
        app.logger.error(f"owner inject error: {e}")
    return resp


def load_tokens(region):
    try:
        if region == "IND":
            with open("token_ind.json", "r") as f:
                tokens = json.load(f)
        elif region in {"BR", "US", "SAC", "NA"}:
            with open("token_br.json", "r") as f:
                tokens = json.load(f)
        else:
            with open("token_bd.json", "r") as f:
                tokens = json.load(f)
        return tokens
    except Exception as e:
        app.logger.error(f"Error loading tokens for region {region}: {e}")
        return None


def encrypt_message(plaintext):
    try:
        key = b'Yg&tc%DEuh6%Zc^8'
        iv = b'6oyZDr22E3ychjM%'
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded_message = pad(plaintext, AES.block_size)
        encrypted_message = cipher.encrypt(padded_message)
        return binascii.hexlify(encrypted_message).decode('utf-8')
    except Exception as e:
        app.logger.error(f"Error encrypting message: {e}")
        return None


def create_protobuf_message(user_id, region):
    try:
        message = like_pb2.like()
        message.uid = int(user_id)
        message.region = region
        return message.SerializeToString()
    except Exception as e:
        app.logger.error(f"Error creating protobuf message: {e}")
        return None


async def send_request(session, encrypted_uid, token, url):
    try:
        edata = bytes.fromhex(encrypted_uid)
        headers = {
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Expect": "100-continue",
            "X-Unity-Version": "2018.4.11f1",
            "X-GA": "v1 1",
            "ReleaseVersion": "OB55"
        }
        async with session.post(url, data=edata, headers=headers) as response:
            return await response.text()
    except Exception as e:
        app.logger.error(f"Exception in send_request: {e}")
        return None


async def send_multiple_requests(uid, region, url):
    try:
        protobuf_message = create_protobuf_message(uid, region)
        if protobuf_message is None:
            return None
        encrypted_uid = encrypt_message(protobuf_message)
        if encrypted_uid is None:
            return None
        tokens = load_tokens(region)
        if tokens is None:
            return None
        # ✅ Use EVERY token in the file exactly once (none skipped)
        token_list = [t["token"] for t in tokens if isinstance(t, dict) and t.get("token")]
        if not token_list:
            return None
        connector = aiohttp.TCPConnector(limit=100)
        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = [send_request(session, encrypted_uid, tk, url) for tk in token_list]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
    except Exception as e:
        app.logger.error(f"Exception in send_multiple_requests: {e}")
        return None


def create_protobuf(uid):
    try:
        message = uid_generator_pb2.uid_generator()
        message.saturn_ = int(uid)
        message.garena = 1
        return message.SerializeToString()
    except Exception as e:
        app.logger.error(f"Error creating uid protobuf: {e}")
        return None


def enc(uid):
    protobuf_data = create_protobuf(uid)
    if protobuf_data is None:
        return None
    return encrypt_message(protobuf_data)


def make_request(encrypt, region, token):
    try:
        if region == "IND":
            url = "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"
        elif region in {"BR", "US", "SAC", "NA"}:
            url = "https://client.us.freefiremobile.com/GetPlayerPersonalShow"
        else:
            url = "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow"
        edata = bytes.fromhex(encrypt)
        headers = {
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Expect": "100-continue",
            "X-Unity-Version": "2018.4.11f1",
            "X-GA": "v1 1",
            "ReleaseVersion": "OB55"
        }
        response = requests.post(url, data=edata, headers=headers, verify=False)
        binary = response.content
        decoded = visit_count_pb2.Info()
        decoded.ParseFromString(binary)
        return decoded
    except DecodeError as e:
        app.logger.error(f"DecodeError: {e}")
        return None
    except Exception as e:
        app.logger.error(f"Error in make_request: {e}")
        return None


@app.route('/like', methods=['GET'])
def handle_requests():
    key, kinfo = find_key(request.args.get("key"))
    if not kinfo:
        return {"error": "Invalid or missing API key"}, 401
    if kinfo.get("disabled"):
        return {"error": "This key is disabled. Contact owner."}, 403
    if kinfo["used"] >= kinfo["limit"]:
        return {"error": LIMIT_MSG, "key_limit": kinfo["limit"],
                "key_used": kinfo["used"], "key_remaining": 0}, 403

    uid = request.args.get("uid")
    region = request.args.get("region", "").upper()
    if not uid or not region:
        return {"error": "UID and region are required"}, 400

    try:
        def process_request():
            tokens = load_tokens(region)
            if not tokens:
                raise Exception("Failed to load tokens.")
            token = tokens[0]['token']
            encrypted_uid = enc(uid)
            if encrypted_uid is None:
                raise Exception("Encryption of UID failed.")
            before = make_request(encrypted_uid, region, token)
            if before is None:
                raise Exception("Failed to get initial info.")
            before_like = before.AccountInfo.Likes

            if region == "IND":
                url = "https://client.ind.freefiremobile.com/LikeProfile"
            elif region in {"BR", "US", "SAC", "NA"}:
                url = "https://client.us.freefiremobile.com/LikeProfile"
            else:
                url = "https://clientbp.ggpolarbear.com/LikeProfile"

            asyncio.run(send_multiple_requests(uid, region, url))

            after = make_request(encrypted_uid, region, token)
            if after is None:
                raise Exception("Failed to get final info.")
            after_like = after.AccountInfo.Likes
            like_given = after_like - before_like
            status = 1 if like_given > 0 else 2

            # Count usage only if likes given >= COUNT_MIN_LIKES (no daily reset)
            with _lock:
                keys = load_keys()
                cur = keys.get(key)
                if cur is not None and like_given >= COUNT_MIN_LIKES:
                    cur["used"] += 1
                    cur["last_used"] = int(time.time())
                    save_keys(keys)
                used = cur["used"] if cur else kinfo["used"]
                limit = cur["limit"] if cur else kinfo["limit"]
            remaining = max(limit - used, 0)

            result = OrderedDict([
                ("LikesGivenByAPI", like_given),
                ("LikesafterCommand", after_like),
                ("LikesbeforeCommand", before_like),
                ("PlayerNickname", after.AccountInfo.PlayerNickname),
                ("Level", after.AccountInfo.Levels),
                ("Region", after.AccountInfo.PlayerRegion),
                ("UID", after.AccountInfo.UID),
                ("status", status),
                ("key_limit", limit),
                ("key_used", used),
                ("key_remaining", remaining)
            ])

            return app.response_class(
                response=json.dumps(result, separators=(',', ':')),
                status=200,
                mimetype='application/json'
            )

        return process_request()

    except Exception as e:
        app.logger.error(f"Error: {e}")
        return {"error": str(e)}, 500


@app.route('/remain', methods=['GET'])
def remain_info():
    key, kinfo = find_key(request.args.get("key"))
    if not kinfo:
        return {"error": "Invalid or missing API key"}, 401
    remaining = max(kinfo["limit"] - kinfo["used"], 0)
    data = {"key_limit": kinfo["limit"], "key_used": kinfo["used"], "key_remaining": remaining}
    if remaining == 0:
        data["message"] = LIMIT_MSG
    return jsonify(data)


# ---------------- ADMIN (owner only) ----------------
def _admin_guard():
    if not admin_ok(request.args.get("admin")):
        return {"error": "Unauthorized"}, 401
    return None


@app.route('/admin/addkey', methods=['GET'])
def admin_addkey():
    g = _admin_guard()
    if g: return g
    name = request.args.get("key") or ("FLEX-" + secrets.token_hex(8).upper())
    limit = int(request.args.get("limit", DEFAULT_LIMIT))
    with _lock:
        keys = load_keys()
        if name in keys:
            return {"error": "Key already exists"}, 400
        keys[name] = {"limit": limit, "used": 0, "disabled": False,
                      "note": request.args.get("note", ""), "created": int(time.time())}
        save_keys(keys)
    return {"key": name, "limit": limit, "used": 0}


@app.route('/admin/renew', methods=['GET'])
def admin_renew():
    """Reset usage to 0 (optionally set a new limit)."""
    g = _admin_guard()
    if g: return g
    name = request.args.get("key")
    with _lock:
        keys = load_keys()
        if name not in keys:
            return {"error": "Key not found"}, 404
        keys[name]["used"] = 0
        if request.args.get("limit"):
            keys[name]["limit"] = int(request.args["limit"])
        save_keys(keys)
    return {"key": name, **keys[name]}


@app.route('/admin/delkey', methods=['GET'])
def admin_delkey():
    g = _admin_guard()
    if g: return g
    name = request.args.get("key")
    with _lock:
        keys = load_keys()
        if keys.pop(name, None) is None:
            return {"error": "Key not found"}, 404
        save_keys(keys)
    return {"deleted": name}


@app.route('/admin/keys', methods=['GET'])
def admin_keys():
    g = _admin_guard()
    if g: return g
    return jsonify({"keys": load_keys()})


@app.route('/adminpoint', methods=['GET'])
def adminpoint():
    """/adminpoint?key=ADMIN_KEY -> সব admin command + সব user/key দেখায়। ভুল key হলে কিছুই দেখাবে না।"""
    if not admin_ok(request.args.get("key")):
        return {"error": "Unauthorized"}, 401
    base = request.host_url.rstrip("/")
    a = request.args.get("key")
    keys = load_keys()
    users = []
    for k, v in keys.items():
        users.append(OrderedDict([
            ("key", k),
            ("limit", v.get("limit", 0)),
            ("used", v.get("used", 0)),
            ("remaining", max(v.get("limit", 0) - v.get("used", 0), 0)),
            ("disabled", v.get("disabled", False)),
            ("note", v.get("note", "")),
        ]))
    commands = OrderedDict([
        ("add_key", f"{base}/admin/addkey?admin={a}&key=NAME&limit=120&note=optional"),
        ("renew_key", f"{base}/admin/renew?admin={a}&key=NAME&limit=120"),
        ("delete_key", f"{base}/admin/delkey?admin={a}&key=NAME"),
        ("all_keys_raw", f"{base}/admin/keys?admin={a}"),
        ("user_like", f"{base}/like?key=USERKEY&uid=UID&region=BD"),
        ("user_remain", f"{base}/remain?key=USERKEY"),
    ])
    return OrderedDict([
        ("total_users", len(users)),
        ("commands", commands),
        ("users", users),
    ])


if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
