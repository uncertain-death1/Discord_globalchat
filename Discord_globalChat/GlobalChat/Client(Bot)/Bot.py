import asyncio
# Discord imports
import discord as ds
from discord.ext import commands as cmds
from discord import app_commands as acmds
import json as jsn
import os

# Path to the JSON file
jsnfp = r'C:\Users\jjfir\python\discord_bots\GlobalChat\Server(Host)\opted_out_guilds\optouts.json'
optouts = []  # To track which servers have opted out of global chat
global_chat_channels = {}  # To store global chat channels for each server

# Check if the JSON file exists and load it
if os.path.exists(jsnfp):
    try:
        with open(jsnfp, 'r') as jsnfile:
            data = jsn.load(jsnfile)
            optouts = data.get('optedOutIds', [])  # Get the list or default to empty
            global_chat_channels = data.get('globalChatChannels', {})  # Get global chat channels
    except (jsn.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error loading JSON file: {e}")
        # If there's an error, initialize optouts to an empty list
        optouts = []
else:
    # Create the JSON file with initial structure if it doesn't exist
    with open(jsnfp, 'w') as jsnfile:
        jsn.dump({'optedOutIds': [], 'globalChatChannels': {}}, jsnfile)

TOKEN = ''  # Add your bot token here
SERVER_IP = '127.0.0.1'  # IP of your socket server
SERVER_PORT = 8888       # Port of your socket server

# Set up the bot
intents = ds.Intents.default()
intents.message_content = True
intents.guilds = True  # Required to receive guild-related events
intents.messages = True  # Required for message handling
client = cmds.Bot(command_prefix=None, intents=intents)

async def connect_to_server():
    global reader, writer
    reader, writer = await asyncio.open_connection(SERVER_IP, SERVER_PORT)

@client.event
async def on_guild_join(guild):
    if guild.id in optouts:
        return

    existing_channel = ds.utils.get(guild.text_channels, name="global-chat")
    if not existing_channel:
        channel = await guild.create_text_channel('global-chat')
        global_chat_channels[guild.id] = channel.id
        print(f"Created 'global-chat' channel in {guild.name}")
    else:
        global_chat_channels[guild.id] = existing_channel.id

@client.event
async def on_ready():
    print(f'Logged in as {client.user}!')
    await client.tree.sync()
    await connect_to_server()
    client.loop.create_task(listen_to_server())

    for guild in client.guilds:
        if guild.id in optouts:
            continue
        existing_channel = ds.utils.get(guild.text_channels, name="global-chat")
        if existing_channel:
            global_chat_channels[guild.id] = existing_channel.id

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('!globalchat'):
        chat_message = message.content[len('!globalchat '):].strip()

        if writer and message.guild.id not in optouts:
            writer.write(f"{message.guild.name}: {message.author.name}: {chat_message}\n".encode())
            await writer.drain()
            print(f"Sent message to server: {chat_message}")  # Debug log

async def listen_to_server():
    global reader
    while True:
        try:
            if reader:
                data = await reader.read(100)
                if data:
                    message = data.decode().strip()  # Clean the message

                    if not message:
                        print("Received an empty message from the server.")  # Debug log
                        continue

                    print(f"Received message from server: {message}")  # Debug log

                    for guild in client.guilds:
                        if guild.id in optouts:
                            print(f"Skipping guild {guild.name} due to opt-out.")  # Debug log
                            continue

                        channel_id = global_chat_channels.get(guild.id)
                        if channel_id:
                            channel = client.get_channel(channel_id)
                            if channel:
                                try:
                                    await channel.send(f"[Global Chat] {message}")
                                    print(f"Sent message to {guild.name}: [Global Chat] {message}")  # Debug log
                                except ds.Forbidden:
                                    print(f"Permission denied to send message in {guild.name}.")  # Debug log
                                except ds.HTTPException as e:
                                    print(f"Failed to send message in {guild.name}: {e}")  # Debug log
                            else:
                                print(f"Channel with ID {channel_id} not found in guild {guild.name}.")  # Debug log
                        else:
                            print(f"No global chat channel set for guild {guild.name}.")  # Debug log

        except Exception as e:
            print(f"Error receiving from server: {e}")


# Command to opt out of global chat
@client.tree.command(name="opt_out", description="Opt out of global chat")
async def opt_out(i: ds.Interaction):
    await i.response.defer(ephemeral=True)
    if i.user.id != i.guild.owner_id:
        await i.followup.send("You are not the server owner!")
    else:
        if i.guild.id not in optouts:
            optouts.append(i.guild.id)
            with open(jsnfp, 'w') as jsnfile:
                jsn.dump({'optedOutIds': optouts, 'globalChatChannels': global_chat_channels}, jsnfile)
            await i.followup.send("You have opted out of global chat.")
        else:
            await i.followup.send("You are already opted out.")

# Command to opt back into global chat
@client.tree.command(name="opt_in", description="Opt in to global chat")
async def opt_in(i: ds.Interaction):
    await i.response.defer(ephemeral=True)
    if i.user.id != i.guild.owner_id:
        await i.followup.send("You are not the server owner!")
    else:
        if i.guild.id in optouts:
            optouts.remove(i.guild.id)
            with open(jsnfp, 'w') as jsnfile:
                jsn.dump({'optedOutIds': optouts, 'globalChatChannels': global_chat_channels}, jsnfile)

            existing_channel = ds.utils.get(i.guild.text_channels, name="global-chat")
            if not existing_channel:
                channel = await i.guild.create_text_channel('global-chat')
                global_chat_channels[i.guild.id] = channel.id
                await i.followup.send("You have opted back into global chat and the 'global-chat' channel has been created.")
            else:
                global_chat_channels[i.guild.id] = existing_channel.id
                await i.followup.send("You have opted back into global chat.")
        else:
            await i.followup.send("You are already opted in.")

# Command to set the global chat channel
@client.tree.command(name="set_global_chat", description="Set the global chat channel for this server")
async def set_global_chat(i: ds.Interaction):
    await i.response.defer(ephemeral=True)
    if i.user.id != i.guild.owner_id:
        await i.followup.send("You are not the server owner!")
        return

    existing_channel = ds.utils.get(i.guild.text_channels, name="global-chat")
    if existing_channel:
        global_chat_channels[i.guild.id] = existing_channel.id
        await i.followup.send(f"'global-chat' channel is already set with ID {existing_channel.id}.")
    else:
        channel = await i.guild.create_text_channel('global-chat')
        global_chat_channels[i.guild.id] = channel.id
        await i.followup.send("Created 'global-chat' channel.")

    with open(jsnfp, 'w') as jsnfile:
        jsn.dump({'optedOutIds': optouts, 'globalChatChannels': global_chat_channels}, jsnfile)

# Run the bot
client.run(TOKEN)
