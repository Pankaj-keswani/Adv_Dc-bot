import discord
from discord.ext import commands
import yt_dlp
import asyncio
import logging

log = logging.getLogger("bot")

# Suppress yt-dlp logging
yt_dlp.utils.bug_reports_message = lambda: ''

# yt-dlp configuration
# Using scsearch (SoundCloud) by default to bypass YouTube's aggressive IP blocks on cloud servers like Azure.
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'scsearch',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')
        self.thumbnail = data.get('thumbnail')
        self.duration = data.get('duration', 0)
        self.uploader = data.get('uploader', 'Unknown')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):
        loop = loop or asyncio.get_event_loop()
        
        # If it's a simple search term, enforce scsearch (SoundCloud) to avoid YouTube blocking
        if not url.startswith('http://') and not url.startswith('https://') and not url.startswith('scsearch:') and not url.startswith('ytsearch:'):
            url = f"scsearch:{url}"
            
        import functools
        try:
            data = await loop.run_in_executor(None, functools.partial(ytdl.extract_info, url, download=not stream))
        except Exception as e:
            log.error(f"Error extracting info from yt-dlp: {e}")
            return None

        if data is None:
            return None

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {} # guild_id -> list of YTDLSource objects
        self.current_playing = {} # guild_id -> YTDLSource object

    def get_queue(self, ctx):
        if ctx.guild.id not in self.queues:
            self.queues[ctx.guild.id] = []
        return self.queues[ctx.guild.id]

    def play_next(self, ctx):
        queue = self.get_queue(ctx)
        if len(queue) > 0:
            player = queue.pop(0)
            self.current_playing[ctx.guild.id] = player
            ctx.voice_client.play(player, after=lambda e: self.play_next(ctx))
            
            # Create embed for now playing
            embed = discord.Embed(title="🎶 Now Playing", description=f"**{player.title}**", color=discord.Color.blue())
            if player.thumbnail:
                embed.set_thumbnail(url=player.thumbnail)
            
            # Send the message using asyncio since we are in a sync callback
            coro = ctx.send(embed=embed)
            asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
        else:
            self.current_playing[ctx.guild.id] = None
            # Disconnect if queue is empty
            coro = ctx.voice_client.disconnect()
            asyncio.run_coroutine_threadsafe(coro, self.bot.loop)

    @commands.command(name="play", aliases=["p", "playmusic"])
    async def play(self, ctx, *, url: str):
        """Plays a song. Uses SoundCloud by default to bypass blocks."""
        async with ctx.typing():
            if not ctx.message.author.voice:
                await ctx.send("❌ You are not connected to a voice channel.")
                return
            
            channel = ctx.message.author.voice.channel

            # Connect to voice channel if not already connected
            if not ctx.voice_client:
                try:
                    await channel.connect()
                except Exception as e:
                    await ctx.send(f"❌ Could not connect to voice channel: {e}")
                    return
            elif ctx.voice_client.channel != channel:
                await ctx.voice_client.move_to(channel)

            # Get player info
            try:
                player = await YTDLSource.from_url(url, loop=self.bot.loop, stream=True)
            except Exception as e:
                log.error(f"Error extracting audio: {e}")
                player = None

            if not player:
                await ctx.send(f"❌ Could not find or play the track: `{url}`. Try being more specific.")
                return

            queue = self.get_queue(ctx)
            queue.append(player)

            if not ctx.voice_client.is_playing():
                self.play_next(ctx)
                await ctx.send(f"✅ Added **{player.title}** to queue and starting playback!")
            else:
                embed = discord.Embed(title="📋 Added to Queue", description=f"**{player.title}**", color=discord.Color.green())
                embed.set_footer(text=f"Position in queue: {len(queue)}")
                await ctx.send(embed=embed)

    @commands.command(name="skip", aliases=["s", "next"])
    async def skip(self, ctx):
        """Skips the currently playing song."""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            await ctx.send("⏭️ Skipped current song.")
        else:
            await ctx.send("❌ Nothing is playing to skip.")

    @commands.command(name="stop", aliases=["leave", "dc", "disconnect"])
    async def stop(self, ctx):
        """Stops playback, clears queue, and leaves voice."""
        if ctx.voice_client:
            self.queues[ctx.guild.id] = []
            self.current_playing[ctx.guild.id] = None
            await ctx.voice_client.disconnect()
            await ctx.send("⏹️ Stopped playing and cleared queue.")
        else:
            await ctx.send("❌ I'm not in a voice channel.")
            
    @commands.command(name="queue", aliases=["q"])
    async def queue(self, ctx):
        """Shows the current music queue."""
        queue = self.get_queue(ctx)
        
        if not queue and not self.current_playing.get(ctx.guild.id):
            return await ctx.send("The queue is currently empty.")
            
        embed = discord.Embed(title=f"Music Queue for {ctx.guild.name}", color=discord.Color.blue())
        
        current = self.current_playing.get(ctx.guild.id)
        if current:
            embed.add_field(name="Currently Playing", value=f"**{current.title}**", inline=False)
            
        if queue:
            queue_text = ""
            for i, track in enumerate(queue[:10]):
                queue_text += f"`{i+1}.` {track.title}\n"
            if len(queue) > 10:
                queue_text += f"\n*...and {len(queue) - 10} more songs*"
                
            embed.add_field(name="Up Next", value=queue_text, inline=False)
            
        await ctx.send(embed=embed)

    @play.error
    async def play_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Please provide a song name or URL! Example: `!play sahiba`")


async def setup(bot):
    await bot.add_cog(Music(bot))
