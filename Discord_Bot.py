import discord
import openai
import os
import asyncio
from pytube import YouTube
from datetime import datetime
from pytz import timezone
from discord.ext import commands
from dotenv import load_dotenv
import random
import string

# Replace with your own bot token and GPT-3 API key
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
openai.api_key = os.getenv('OPENAI_API_KEY')

# Create the Discord bot object with the command prefix "!"
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='/',intents=intents)

# Keep track of voice clients for each server
voice_clients = {}

# Command to list all Commands
@bot.command(name='list_all')
async def all_commands(ctx):
    await ctx.send('/hopin - to join the voice channel user is in currently\n/hopout - to leave the current voice channel\n/play - to play music with given url\n/pause - to pause music\n/resume - to resume music\n/set - to set reminder for gievn date and time\n/show - to list all set reminder\n/rem - to remove a reminder given it\'s index\n/mod - to modify a given reminder at an index to given date and time\n/talk - to talk to me')

# Command to join the voice channel the user is in
@bot.command(name="hopin")
async def join_voice_channel(ctx):
    if not ctx.message.author.voice:
        await ctx.send("You are not connected to a voice channel")
        return
    channel = ctx.message.author.voice.channel
    if ctx.guild.voice_client is not None:
        await ctx.guild.voice_client.move_to(channel)
    else:
        voice_clients[ctx.guild] = await channel.connect()

# Command to leave the voice channel
@bot.command(name="hopout")
async def leave_voice_channel(ctx):
    if ctx.guild.voice_client is not None:
        await ctx.guild.voice_client.disconnect()

# Command to play music from a URL
class MusicPlayer:
    def __init__(self, voice_client):
        self.voice_client = voice_client
        self.queue = []
        self.playing = False
        self.paused = False

    async def add_to_queue(self, url):
        self.queue.append(url)
        await self.voice_client.channel.send('Added to queue.')

    async def play_next_song(self):
        if self.queue:
            next_song_url = self.queue.pop(0)
            player = await YTDLSource.from_url(next_song_url, loop=asyncio.get_event_loop())
            self.voice_client.play(player, after=lambda e: self.handle_player_error(e))
            self.voice_client.source = discord.PCMVolumeTransformer(self.voice_client.source)
            await self.voice_client.channel.send('Now playing: {}'.format(player.title))
        else:
            self.playing = False
            await self.voice_client.disconnect()

    async def handle_player_error(self, error):
        if error:
            await self.voice_client.channel.send(f'Player error: {error}')
        await self.play_next_song()

    async def start_playing(self):
        self.playing = True
        while self.playing:
            if self.voice_client.is_playing():
                await asyncio.sleep(1)
            else:
                await self.play_next_song()
            while self.paused:
                await asyncio.sleep(1)
            #await asyncio.sleep(1)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data):
        super().__init__(source)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.thumbnail = data.get('thumbnail')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        yt = YouTube(url)
        stream = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
        data = {
            'title': yt.title,
            'url': yt.watch_url,
            'thumbnail': yt.thumbnail_url
        }
        def generate_random_string(length):
            letters = string.ascii_lowercase
            return ''.join(random.choice(letters) for _ in range(length))
        random_string = generate_random_string(10)
    
        filename = f"{random_string}.mp4"
        stream.download(filename=filename)
        return cls(discord.FFmpegPCMAudio(filename, executable="ffmpeg"), data=data)

@bot.command(name='play')
async def play(ctx):
    if not ctx.author.voice:
        await ctx.send('You must be in a voice channel to use this command.')
        return

    voice_client = ctx.voice_client
    if voice_client:
        if voice_client.channel != ctx.author.voice.channel:
            await voice_client.disconnect()

    channel = ctx.author.voice.channel
    voice_client = await channel.connect()

    if not hasattr(bot, 'player'):
        bot.player = MusicPlayer(voice_client)

    url = ctx.message.content[6:]
    await bot.player.add_to_queue(url)

    if not bot.player.playing:
        bot.player.playing = True
        await bot.player.start_playing()

@bot.command(name='pause')
async def pause(ctx):
    if not hasattr(bot, 'player'):
        await ctx.send('No song is currently playing.')
        return

    if bot.player.paused:
        await ctx.send('Player already paused.')
    else:
        bot.player.paused = True
        bot.player.voice_client.pause()
        await ctx.send('Player paused.')

@bot.command(name='resume')
async def resume(ctx):
    if not hasattr(bot, 'player'):
        await ctx.send('No song is currently playing.')
        return

    if not bot.player.paused:
        await ctx.send('The song is not paused.')
    else:
        bot.player.paused = False
        bot.player.voice_client.resume()
        await ctx.send('Player resumed.')

# List to hold reminders
reminders = []

# Function to parse message for datetime
def parse_message_for_datetime(message):
    try:
        datetime_str = message.split(' ')[0:2]
        datetime_str = ' '.join(datetime_str)
        return datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return None

# Function to create a reminder
def create_reminder(author_id, datetime):
    reminders.append({'author_id': author_id, 'datetime': datetime})

# Function to delete a reminder
def delete_reminder(index):
    reminders.pop(index)

# Function to modify a reminder
def modify_reminder(index, datetime):
    reminders[index]['datetime'] = datetime

user_timezone = timezone('Asia/Kolkata')  # Replace with the user's timezone

@bot.command(name='set')
async def remind(ctx, *, message):
    # Get the datetime object from the message
    reminder_datetime = parse_message_for_datetime(message)
    if not reminder_datetime:
        await ctx.send("Please enter a valid datetime in the format 'YYYY-MM-DD HH:MM:SS'")
        return

    # Convert the datetime to the user's timezone
    reminder_datetime = reminder_datetime.astimezone(user_timezone)
    
    if datetime.now(timezone('Asia/Kolkata')) >= reminder_datetime:
        await ctx.send("Entered time is in the Past, reminder not set")
    else:
        # Create the reminder
        create_reminder(ctx.author.id, reminder_datetime)

        # Confirm the reminder was set
        formatted_datetime = reminder_datetime.strftime('%Y-%m-%d %H:%M:%S %Z')
        await ctx.send(f"Reminder set for {formatted_datetime}")

# Command to show all reminders
@bot.command(name='show')
async def show_reminders(ctx):
    reminder_str = "Reminders:\n"
    for i, reminder in enumerate(reminders):
        reminder_str += f"{i+1}. {reminder['datetime']} \n"
    await ctx.send(reminder_str)

# Command to delete a reminder
@bot.command(name='rem')
async def delete(ctx, index: int):
    try:
        delete_reminder(index - 1)
        await ctx.send(f"Reminder {index} deleted")
    except IndexError:
        await ctx.send(f"Reminder {index} not found")

# Command to modify a reminder
@bot.command(name='mod')
async def modify(ctx, index: int, datetime_str1: str, datetime_str2: str):
    try:
        datetime_str = datetime_str1+" "+datetime_str2
        datetime_obj = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
        datetime_obj = datetime_obj.astimezone(user_timezone)
        if datetime.now(timezone('Asia/Kolkata')) >= datetime_obj:
            await ctx.send("Entered time is in the Past, reminder not modified")
        else:
            modify_reminder(index - 1, datetime_obj)
            await ctx.send(f"Reminder {index} modified to {datetime_obj}")
    except ValueError:
        await ctx.send("Invalid datetime format")

async def check_reminders():
    while True:
        for i, reminder in enumerate(reminders):
            if datetime.now(timezone('Asia/Kolkata')) >= reminder['datetime']:
                author = await bot.fetch_user(reminder['author_id'])
                await author.send('Reminder: Your Event is Happening')
                delete_reminder(i)
        await asyncio.sleep(1)  # check every 1 seconds

# Define your GPT-3 model
model_engine = "text-davinci-003"

@bot.command(name='talk')
async def on_message(ctx):
    if ctx.author == bot.user:
        return

    # Get the user input
    user_input = ctx.message.content.split("/talk ")[1]

    # Call the OpenAI API to generate a response
    response = openai.Completion.create(
        engine=model_engine,
        prompt=user_input,
        max_tokens=2048,
        n=1,
        stop=None,
        temperature=0.7,
    )

    # Send the response back to the user
    await ctx.send(response.choices[0].text)

# Event listener for when the bot is ready
@bot.event
async def on_ready():
    """print(f"Logged in as {bot.user}")
    print(f"Servers: {', '.join([guild.name for guild in bot.guilds])}")
    print(f"{bot.user} is connected to the following guilds:\n")
    for guild in bot.guilds:
        print(f"{guild.name} (id: {guild.id})")"""
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    bot.loop.create_task(check_reminders())

# Run the bot with your Discord bot token
bot.run(TOKEN) 

#0259bb253341d32829c57b52b211b9c3