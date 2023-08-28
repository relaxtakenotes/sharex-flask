# sharex-flask

A flask based python file server for sharex, with pretty good embed support tailored for discord.

# How to install
- Install python, preferably 3.11
- Install requirements from requirements.txt
- Setup a server like gunicorn, using a command like this: "/home/user/.local/bin/gunicorn -w 4 'app:app' -b 127.0.0.1:47015 --timeout 360", then reverse proxy it through nginx or apache (or even cloudflare tunnels! It's recommended, because you dont want skids ddosing your epic personal website)