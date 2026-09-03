import os
import json
import discord
import requests
from discord.ext import commands, tasks
from rich import print
from dotenv import load_dotenv
from hashlib import sha256
from pathlib import Path
from datetime import datetime

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
base_dir = Path(__file__).resolve().parent

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

def load_config():
    global config
    with open(base_dir / "config.json") as f:
        config = json.load(f)

def save_config():
    global config
    with open(base_dir / "config.json", "w") as f:
        json.dump(config, f, indent=4)

load_config()


@bot.event
async def on_ready():
    print(f"[green]Logged in as \"[bold]{bot.user}[/bold]\"[/green]")

    if not config["scan_channel"]:
        print("[red bold]No output channel assigned![/bold red]")

    if config["scan_loop"] and not scan_web.is_running():
        scan_web.start()


@bot.command(name="scan_help")
async def help(ctx):
    embed = discord.Embed()
    embed.title = "Bot Manual"
    embed.add_field(name="!scan_interval <sec>", value="Changes scan speed [30>x>3600]", inline=True)
    embed.add_field(name="!scan_url <url>", value="Changes url to track [https://...]", inline=True)
    embed.add_field(name="!scan_toggle", value="Toggle whether bot is tracking website", inline=True)
    embed.add_field(name="", value="", inline=False)
    embed.add_field(name="!scan_channel <id>", value="Changes output channel [15450...]", inline=True)
    embed.add_field(name="!scan_config", value="Prints out current config", inline=True)
    embed.color = discord.Color(0xffffff)

    await ctx.send(embed=embed)


@bot.command(name="scan_config")
async def get_config(ctx):
    global config

    parsed = json.dumps(config, indent=4)
    await ctx.send("## Config:\n```json\n" + parsed + "\n```")


@bot.command(name="scan_channel")
async def change_channel(ctx, id:str):
    config["scan_channel"] = id
    save_config()

    embed = discord.Embed()
    embed.title = "Changed output channel!"
    embed.description = f"New output channel is <#{id}>."
    embed.color = discord.Color(0x00ff00)
    await ctx.send(embed=embed)

    print(f"[green]Output channel changed to: [bold]{id}[/bold green]")


@bot.command(name="scan_interval")
async def change_interval(ctx, sec:int):
    inter = min(max(sec, 30), 3600)
    scan_web.change_interval(seconds=inter)

    embed = discord.Embed()
    embed.title = "Changed loop interval!"
    embed.description = f"New loop interval is {inter} seconds."
    embed.color = discord.Color(0x00ff00)
    await ctx.send(embed=embed)

    config["scan_interval"] = inter
    save_config()

    print(f"[green]Loop interval changed to: [bold]{inter}[/bold] sec[/green]")


@bot.command(name="scan_url")
async def change_url(ctx, url:str):
    try:
        requests.get(url.strip())
    except:
        embed = discord.Embed()
        embed.title = "URL provided is invalid!"
        embed.description = "Target Scan URL wasn't changed."
        embed.color = discord.Color(0xff7700)
        await ctx.send(embed=embed)
        print(f"[red] Declined change URL to [bold]{url}[/bold red]")
    else:
        config["scan_url"] = url.strip()
        save_config()

        embed = discord.Embed()
        embed.title = "New Target URL was set!"
        embed.color = discord.Color(0x00ff00)
        await ctx.send(embed=embed)
        print(f"[green] Changed URL to [bold]{url}[/bold green]")


@bot.command(name="scan_loop")
async def scan_toggle(ctx):
    if config["scan_loop"]:
        scan_web.cancel()

        embed = discord.Embed()
        embed.title = "Stopped Loop Checking"
        embed.color = discord.Color(0xff0000)
        await ctx.send(embed=embed)

    else:
        if not scan_web.is_running():
            scan_web.start()

        embed = discord.Embed()
        embed.title = "Started Loop Checking"
        embed.color = discord.Color(0x00ff00)
        await ctx.send(embed=embed)

    config["scan_loop"] = not config["scan_loop"]
    save_config()


@tasks.loop(seconds=config["scan_interval"])
async def scan_web():
    if not config["scan_url"]:
        embed = discord.Embed()
        embed.title = "No Link is assigned to track!"
        embed.description = "Bot will stop attempts to track until new link is assigned."
        embed.color = discord.Color(0xff0000)
        await bot.get_channel(config["scan_channel"]).send(embed=embed)

    else:
        response = requests.get(config["scan_url"])
        if not response.text:
            print("[red]Error while scanning: [bold]Response is empty[/bold red]")
            return
        elif response.status_code != 200:
            if not config["is_broken"]:
                embed = discord.Embed()
                embed.title = "Website broke!"
                embed.color = discord.Color(0xcc0000)
                await bot.get_channel(config["scan_channel"]).send(embed=embed)

                config["is_broken"] = True
                save_config()
            print(f"[red]Error while scanning: [bold]Status code: {response.status_code}[/bold red]")
            return
        elif config["is_broken"] and response.status_code == 200:
            embed = discord.Embed()
            embed.title = "Website got fixed!"
            embed.color = discord.Color(0x00cc00)
            await bot.get_channel(config["scan_channel"]).send(embed=embed)

            config["is_broken"] = False
            save_config()

            print("[green]Website is working now![/green]")
            return

        hashed = sha256(response.text.encode("utf-8")).hexdigest()
        with open(base_dir / "latest.txt") as f:
            if hashed != f.read():
                text = str(response.text)
                file_name = datetime.now().strftime("%Y-%m-%d_%H-%M-%S.html")

                with open(base_dir / "dumps" / file_name, "w", encoding="utf-8") as d:
                    d.write(text)
                with open(base_dir / "latest.txt", "w") as f:
                    f.write(hashed)

                embed = discord.Embed()
                embed.title = "URL GOT CHANGED"
                embed.description = "Dump was saved."
                embed.color = discord.Color(0x0077ff)

                await bot.get_channel(config["scan_channel"]).send(embed=embed)


bot.run(DISCORD_TOKEN)