import secrets
import json

CONFIG_PATH = "configs/main.json"

name = input("Input the user name: ")
embed_enabled = input("Do you want embeds? (true/false): ")
embed_color = input("Input the custom embed color in hex format, but without the hashtag: ")
embed_description = input("Input the custom description (%filename% %filesize% %username%): ")
embed_title = input("Input the custom title (%filename% %filesize% %username%): ")
secret_key = secrets.token_urlsafe(32)

with open(CONFIG_PATH) as f:
    cfg = json.load(f)
    cfg["authorization"][name] = secret_key

with open(CONFIG_PATH, "w") as f:
    json.dump(cfg, f, indent=4)

with open(f"{name}.sxcu", "w+") as f:
    with open(f"template._sxcu") as g:
        output = g.read()
    output = (output.replace("%name%", name)
                    .replace("%secret%", secret_key)
                    .replace("%DOMAIN%", cfg["domain"])
                    .replace("%embed_enabled%", embed_enabled)
                    .replace("%embed_color%", embed_color)
                    .replace("%embed_title%", embed_title)
                    .replace("%embed_description%", embed_description))
    print(output)
    f.write(output)