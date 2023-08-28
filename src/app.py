# custom
from flask import Flask as flask
from flask import request, send_file
from pydub import AudioSegment
import ffmpeg

# local/default
import json
import re
import os
import urllib.parse
import secrets
import requests
import subprocess
import shlex
import shutil
import traceback
import pickle

CONFIG_PATH = "configs/main.json"
UPLOADS_PATH = "configs/uploads.bin"
PAGES_DIR = "pages/"
SAVE_DIR = "files/"
FILETYPES = {
    ".mp3": "audio",
    ".ogg": "audio",
    ".flac": "audio",
    ".mp4": "video",
    ".webm": "video",
    ".jpeg": "image",
    ".jpg": "image",
    ".png": "image",
    ".gif": "image",
    ".webp": "image"
}

if not os.path.isfile(UPLOADS_PATH):
    with open(UPLOADS_PATH, "wb+") as f:
        pickle.dump({}, f)

if not os.path.isdir(SAVE_DIR):
    os.mkdir(SAVE_DIR)

with open(CONFIG_PATH) as f:
    config = json.load(f)

app = flask(__name__)

pages = {}
for file in [PAGES_DIR + f for f in os.listdir(PAGES_DIR) if os.path.isfile(PAGES_DIR + f)]:
    name, ext = os.path.splitext(file)
    name = os.path.basename(name)
    with open(file) as f:
        pages[name] = f.read()

def webhook_log(content):
    try:
        data = {
            "content": content,
            "username": "sharex-flask"
        }
        result = requests.post(config["webhook_url"], json=data)
    except Exception:
        pass # dont care

def get_size(fobj):
    if fobj.content_length:
        return fobj.content_length

    try:
        pos = fobj.tell()
        fobj.seek(0, 2)  #seek to end
        size = fobj.tell()
        fobj.seek(pos)  # back to original position
        return size
    except (AttributeError, IOError):
        pass

    # in-memory file object that doesn't support seeking or tell
    return 0  #assume small enough

def shell_exec(command):
    p = subprocess.Popen(shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()
    return p[0].decode("utf-8", errors="ignore")

def convert_to_mp4(mkv_file):
    name, ext = os.path.splitext(mkv_file)
    out_name = name + ".mp4"
    ffmpeg.input(mkv_file).output(out_name).run()
    return out_name

def convert_mp3_to_mp4(mp3_file):
    name, ext = os.path.splitext(mp3_file)
    out_name = name + ".mp4"
    # TODO: look into ways to exploit this and then fix it :-)
    shell_exec(f"ffmpeg -f lavfi -i color=c=black:s=640x240:r=5 -i \"{mp3_file}\" -crf 0 -c:a copy -shortest \"{out_name}\"")
    return out_name

def get_thumbnail(mp4_file):
    name, ext = os.path.splitext(mp4_file)
    out_name = name + ".jpg"
    shell_exec(f"ffmpeg -i \"{mp4_file}\" -ss 00:00:01.000 -vframes 1 \"{out_name}\"")
    return out_name

def get_video_dimensions(mp4_file):
    output = shell_exec(f"ffprobe -v error -select_streams v -show_entries stream=width,height -of csv=p=0:s=x \"{mp4_file}\"")
    return output.split("x")

def generate_response(data, status_code=200):
    response = app.response_class(response=json.dumps(data), status=status_code, mimetype="application/json")
    return response

def get_upload(code):
    uploads = {}

    with open(UPLOADS_PATH, "rb") as f:
        uploads = pickle.load(f)

    return uploads.get(code)    

@app.route('/', methods=['GET'])
def index():
    return pages["index"]

@app.route('/<code>/delete/<key>/', methods=['GET'])
def delete(code, key):
    args = request.args

    upload = get_upload(code)

    if not upload:
        return "not found"

    url = config["domain"] + "/" + code

    if key == upload.get("deletion_key"):
        webhook_log(f"```--- Upload Deleted ---\nUser: {upload.get('owner')}\nURL: {url}```")

        shutil.rmtree(f"{SAVE_DIR}/{code}/")

        uploads = {}

        with open(UPLOADS_PATH, "rb") as f:
            uploads = pickle.load(f)

        if uploads.get(code):
            del uploads[code]

        with open(UPLOADS_PATH, "wb") as f:
            pickle.dump(uploads, f)

        return "deleted"

    return "nope!"

@app.route('/<code>', methods=['GET'])
def download(code):
    args = request.args
    
    upload = get_upload(code)

    if not upload:
        return "not found"

    url = config["domain"] + "/" + code

    def formatt(upload, inputt, extension=False):
        filename = upload.get("name")
        if extension:
            filename = os.path.basename(upload.get("save_path"))
        return (inputt.replace("%filename%", filename)
                        .replace("%filesize%", upload.get("file_size"))
                        .replace("%username%", upload.get("owner")))

    if upload.get("embed_enabled") == "false":
        return send_file(upload.get("save_path"), download_name=os.path.basename(upload.get("save_path")))

    # todo: do it prettier. walls of text scare me
    match upload.get("type"):
        case "audio":
            page = pages["audio_embed"]
            title = formatt(upload, upload.get("embed_title"), extension=False)
            description = formatt(upload, upload.get("embed_description"), extension=False)
            page = (page.replace("{title}", title)
                        .replace("{string_duration}", upload.get("str_dur"))
                        .replace("{file_url}", url + "/raw" + upload.get("extension"))
                        .replace("{real_url}", url + "/converted.mp4")
                        .replace("{thumbnail}", url + "/thumbnail.jpg")
                        .replace("{width}", upload.get("width"))
                        .replace("{height}", upload.get("height"))
                        .replace("{embed_color}", upload.get("embed_color"))
                        .replace("{description}", description))

            return page
        case "video":
            page = pages["video_embed"]
            title = formatt(upload, upload.get("embed_title"), extension=False)
            description = formatt(upload, upload.get("embed_description"), extension=False)
            page = (page.replace("{title}", title)
                        .replace("{file_url}", url + "/raw" + upload.get("extension"))
                        .replace("{file_type}", upload.get("content_type"))
                        .replace("{thumbnail}", url + "/thumbnail.jpg")
                        .replace("{width}", upload.get("width"))
                        .replace("{height}", upload.get("height"))
                        .replace("{embed_color}", upload.get("embed_color"))
                        .replace("{description}", description))

            return page
        case "other":
            page = pages["file_embed"]
            title = formatt(upload, upload.get("embed_title"), extension=True)
            description = formatt(upload, upload.get("embed_description"), extension=True)
            page = (page.replace("{title}", title)
                        .replace("{file_url}", url + "/raw" + upload.get("extension"))
                        .replace("{embed_color}", upload.get("embed_color"))
                        .replace("{description}", description))

            return page
        case "image":
            page = pages["image_embed"]
            title = formatt(upload, upload.get("embed_title"), extension=False)
            description = formatt(upload, upload.get("embed_description"), extension=False)
            page = (page.replace("{title}", title)
                        .replace("{file_url}", url + "/raw" + upload.get("extension"))
                        .replace("{embed_color}", upload.get("embed_color"))
                        .replace("{description}", description))

            return page
        case _:
            pass

@app.route('/<code>/thumbnail.jpg', methods=['GET'])
def download_thumbnail(code):
    upload = get_upload(code)

    if not upload:
        return "not found"

    return send_file(upload.get("thumbnail"), download_name=os.path.basename(upload.get("thumbnail")))

# see below. urgh
@app.route('/<code>/raw.<extension>', methods=['GET'])
def download_raw(code, extension):
    upload = get_upload(code)

    if not upload:
        return "not found"

    return send_file(upload.get("save_path"), download_name=os.path.basename(upload.get("save_path")))

# i dont even need the extension it's just discord who keeps bugging me about it URGH
@app.route('/<code>/converted.<extension>', methods=['GET'])
def download_converted(code, extension):
    upload = get_upload(code)

    if not upload:
        return "not found"

    if upload.get("converted"):
        return send_file(upload.get("converted"), download_name=os.path.basename(upload.get("converted")))
    
    return send_file(upload.get("save_path"), download_name=os.path.basename(upload.get("save_path")))  

@app.route('/upload', methods=['POST'])
def upload():
    try:
        args = request.args

        if config.get("authorization").get(args.get("name")) != args.get("password"):
            return generate_response({"status": "invalid auth"}, status_code=400)

        # get current uploads
        uploads = {}

        with open(UPLOADS_PATH, "rb") as f:
            uploads = pickle.load(f)

        # get file, name, extension, type, owner and deletion key
        content = request.files["content"]
        name, extension = os.path.splitext(os.path.basename(content.filename))
        typee = FILETYPES.get(extension, "other")
        owner = args.get("name")
        deletion_key = secrets.token_urlsafe(64)
        file_size = str(round(get_size(content) / (1024 ** 2), 2)) + "MB"

        # reject if conditions are not met
        allowed_filetypes = config.get("allowed_filetypes")
        if len(allowed_filetypes) > 0 and extension not in allowed_filetypes:
            return generate_response({"status": "extension not allowed"}, status_code=400)

        # todo: implement filesize checking

        # save in a free slot
        code = secrets.token_urlsafe(6)
        while uploads.get(code):
            code = secrets.token_urlsafe(6)
        save_directory = os.path.join(SAVE_DIR, code + "/")
        os.mkdir(save_directory)
        save_path = os.path.join(save_directory, content.filename.replace("/", "").replace("\\", ""))
        content.save(save_path)

        # process custom embed parameters
        def sanitize(inputt):
            return inputt.replace("<", "").replace(">", "").replace("\"", "")

        embed_enabled = sanitize(args.get("embed_enabled", "false"))
        embed_color = sanitize(args.get("embed_color", "000000"))
        embed_title = sanitize(args.get("embed_title", "%filename%"))
        embed_description = sanitize(args.get("embed_description", ""))

        # convert if needed
        converted = ""
        if round(os.path.getsize(save_path)*0.000001) < 100:
            if extension == ".mkv":
                save_path = convert_to_mp4(save_path)
            if typee == "audio" and embed_enabled == "true":
                converted = convert_mp3_to_mp4(save_path)

        # get some file type specific data for embeds
        thumbnail = ""
        width, height = "", ""
        string_duration = ""
        if embed_enabled == "true":
            if typee == "video":
                thumbnail = get_thumbnail(save_path)
                width, height = get_video_dimensions(save_path)

            if typee == "audio":
                thumbnail = get_thumbnail(converted)
                width, height = get_video_dimensions(converted)

                sound = AudioSegment.from_file(save_path)
                sound.duration_seconds == (len(sound) / 1000.0)
                minutes_duartion = str(int(sound.duration_seconds // 60))
                seconds_duration = str(int(sound.duration_seconds % 60))
                string_duration = minutes_duartion+':'+seconds_duration
        
        # add our new upload to uploads.json
        # i'm turning all of them into a string in case they turn into a different type. i dont want that because we're not serializing into json, but raw binary
        uploads[code] = {
            "name": str(name),
            "extension": str(extension),
            "save_path": str(save_path),
            "owner": str(owner),
            "deletion_key": str(deletion_key),
            "type": str(typee),
            "converted": str(converted),
            "thumbnail": str(thumbnail),
            "content_type": str(content.content_type),
            "width": str(width),
            "height": str(height),
            "str_dur": str(string_duration),
            "file_size": str(file_size),
            "embed_enabled": str(embed_enabled),
            "embed_color": str(embed_color),
            "embed_title": str(embed_title),
            "embed_description": str(embed_description)
        }

        with open(UPLOADS_PATH, "wb") as f:
            pickle.dump(uploads, f)

        # log it and send it to the requester
        url = config["domain"] + "/" + code
        delete_url = url + "/delete/" + deletion_key + "/"
        data = {"url": url, "delete": delete_url}

        webhook_log(f"{url} \n```--- New Upload ---\nUser: {owner}\nDeletion URL: {delete_url}\nFilename: {name}{extension}\nConverted: {bool(converted)}```")

        return generate_response(data, status_code=200)
    except Exception:
        webhook_log(f"```{traceback.format_exc()}```")

if __name__ == "__main__":
    app.run(debug=True)