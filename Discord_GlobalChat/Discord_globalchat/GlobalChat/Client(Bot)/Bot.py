import asyncio
import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import conf

# Path to the JSON file
json_fp = r'/Users/wextraaa/Discord_GlobalChat/Discord_globalchat/GlobalChat/Server(Host)/opted_out_guilds/optouts.json'
optouts = []  # To track which servers have opted out of global chat
global_chat_channels = {}  # To store global chat channels for each server

# Check if the JSON file exists and load it
if os.path.exists(json_fp):
    try:
        with open(json_fp, 'r') as jsnfile:
            data = json.load(jsnfile)
            optouts = data.get('optedOutIds', [])  # Get the list or default to empty
            global_chat_channels = data.get('globalChatChannels', {})  # Get global chat channels
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error loading JSON file: {e}")
        optouts = []  # Initialize optouts to an empty list if an error occurs
else:
    # Create the JSON file with initial structure if it doesn't exist
    with open(json_fp, 'w') as jsnfile:
        json.dump({'optedOutIds': [], 'globalChatChannels': {}}, jsnfile)

SERVER_IP = '127.0.0.1'  # IP of your socket server
SERVER_PORT = 8888       # Port of your socket server

# Set up the bot with intents
intents = discord.Intents.all()
# intents.message_content = True
# intents.guilds = True  # Required to receive guild-related events
# intents.messages = True  # Required for message handling
bot = commands.Bot(command_prefix="!", intents=intents)  # Added command_prefix for prefixed commands

async def connect_to_server():
    global reader, writer
    try:
        reader, writer = await asyncio.open_connection(SERVER_IP, SERVER_PORT)
    except Exception as e:
        print(f"Failed to connect to the server: {e}")
        reader, writer = None, None

@bot.event
async def on_guild_join(guild: discord.Guild):
    if guild.id in optouts:
        return

    existing_channel = discord.utils.get(guild.text_channels, name="global-chat")
    if not existing_channel:
        channel = await guild.create_text_channel('global-chat')
        global_chat_channels[guild.id] = channel.id
        print(f"Created 'global-chat' channel in {guild.name}")
    else:
        global_chat_channels[guild.id] = existing_channel.id

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')
    await bot.tree.sync()
    await connect_to_server()
    bot.loop.create_task(listen_to_server())

    for guild in bot.guilds:
        if guild.id in optouts:
            continue
        existing_channel = discord.utils.get(guild.text_channels, name="global-chat")
        if existing_channel:
            global_chat_channels[guild.id] = existing_channel.id

@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
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

                    for guild in bot.guilds:
                        if guild.id in optouts:
                            print(f"Skipping guild {guild.name} due to opt-out.")  # Debug log
                            continue

                        channel_id = global_chat_channels.get(guild.id)
                        if channel_id:
                            channel = bot.get_channel(channel_id)
                            if channel:
                                try:
                                    await channel.send(f"[Global Chat] {message}")
                                    print(f"Sent message to {guild.name}: [Global Chat] {message}")  # Debug log
                                except discord.Forbidden:
                                    print(f"Permission denied to send message in {guild.name}.")  # Debug log
                                except discord.HTTPException as e:
                                    print(f"Failed to send message in {guild.name}: {e}")  # Debug log
                            else:
                                print(f"Channel with ID {channel_id} not found in guild {guild.name}.")  # Debug log
                        else:
                            print(f"No global chat channel set for guild {guild.name}.")  # Debug log

        except Exception as e:
            print(f"Error receiving from server: {e}")

# Save changes to JSON file safely
def save_to_json():
    with open(json_fp, 'w') as jsnfile:
        json.dump({'optedOutIds': optouts, 'globalChatChannels': global_chat_channels}, jsnfile)

# Command to opt out of global chat
@bot.tree.command(name="opt_out", description="Opt out of global chat")
async def opt_out(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if interaction.user.id != interaction.guild.owner_id:
        await interaction.followup.send("You are not the server owner!")
    else:
        if interaction.guild.id not in optouts:
            optouts.append(interaction.guild.id)
            save_to_json()
            await interaction.followup.send("You have opted out of global chat.")
        else:
            await interaction.followup.send("You are already opted out.")

# Command to opt back into global chat
@bot.tree.command(name="opt_in", description="Opt in to global chat")
async def opt_in(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if interaction.user.id != interaction.guild.owner_id:
        await interaction.followup.send("You are not the server owner!")
    else:
        if interaction.guild.id in optouts:
            optouts.remove(interaction.guild.id)
            save_to_json()

            existing_channel = discord.utils.get(interaction.guild.text_channels, name="global-chat")
            if not existing_channel:
                channel = await interaction.guild.create_text_channel('global-chat')
                global_chat_channels[interaction.guild.id] = channel.id
                await interaction.followup.send("You have opted back into global chat and the 'global-chat' channel has been created.")
            else:
                global_chat_channels[interaction.guild.id] = existing_channel.id
                await interaction.followup.send("You have opted back into global chat.")
        else:
            await interaction.followup.send("You are already opted in.")

# Command to set the global chat channel
@bot.tree.command(name="set_global_chat", description="Set the global chat channel for this server")
async def set_global_chat(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if interaction.user.id != interaction.guild.owner_id:
        await interaction.followup.send("You are not the server owner!")
        return

    existing_channel = discord.utils.get(interaction.guild.text_channels, name="global-chat")
    if existing_channel:
        global_chat_channels[interaction.guild.id] = existing_channel.id
        await interaction.followup.send(f"'global-chat' channel is already set with ID {existing_channel.id}.")
    else:
        channel = await interaction.guild.create_text_channel('global-chat')
        global_chat_channels[interaction.guild.id] = channel.id
        await interaction.followup.send("Created 'global-chat' channel.")

    save_to_json()

# Run the bot
bot.run(conf.TOKEN)
