"""
cogs/music.py — Reliable music playback for the Discord bot.

Architecture: single-step extraction ensures ffmpeg always gets a valid stream URL.
Voice connection is protected by a per-guild asyncio.Lock to prevent race conditions.
"""

import discord
from discord.ext import commands
import yt_dlp
import asyncio
import logging
import functools
import traceback

log = logging.getLogger("bot")

# ── yt-dlp configuration ────────────────────────────────────────────────────────

YTDL_OPTS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'socket_timeout': 15,
    'extractor_args': {'youtube': {'skip': ['dash', 'hls']}},
}

# ffmpeg flags: tell it to auto-reconnect if the stream drops mid-song
FFMPEG_OPTS = {
    'before_options': (
        '-reconnect 1 '
        '-reconnect_streamed 1 '
        '-reconnect_delay_max 5'
    ),
    'options': '-vn',
}

ytdl = yt_dlp.YoutubeDL(YTDL_OPTS)


# ── Source class ────────────────────────────────────────────────────────────────

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title', 'Unknown')
        self.url = data.get('webpage_url', data.get('url', ''))
        self.thumbnail = data.get('thumbnail')
        self.duration = data.get('duration')

    @classmethod
    async def from_search(cls, search: str, *, loop=None, volume=0.5):
        """
        Full single-step extraction:
        1. Search / resolve the URL.
        2. Pick the best audio format.
        3. Return a ready-to-play YTDLSource.
        """
        loop = loop or asyncio.get_event_loop()

        # Decide search prefix
        if not search.startswith(('http://', 'https://')):
            query = f'ytsearch:{search}'
        else:
            query = search

        try:
            data = await loop.run_in_executor(
                None,
                functools.partial(ytdl.extract_info, query, download=False)
            )
        except yt_dlp.utils.DownloadError as e:
            log.error(f"yt-dlp DownloadError: {e}")
            return None
        except Exception as e:
            log.error(f"yt-dlp unexpected error: {e}\n{traceback.format_exc()}")
            return None

        if data is None:
            return None

        # If it returned a playlist wrapper, grab first entry
        if 'entries' in data:
            entries = [e for e in data['entries'] if e]
            if not entries:
                return None
            data = entries[0]

        # Validate we actually have a stream URL
        stream_url = data.get('url')
        if not stream_url:
            log.error(f"yt-dlp returned no stream URL for: {search}")
            return None

        log.info(f"Resolved stream for: {data.get('title', '?')} → {stream_url[:60]}...")

        audio = discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTS)
        return cls(audio, data=data, volume=volume)


# ── Music Cog ───────────────────────────────────────────────────────────────────

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # guild_id → list of search strings
        self.queues: dict[int, list[str]] = {}
        # guild_id → current YTDLSource player
        self.current_playing: dict[int, YTDLSource | None] = {}
        # guild_id → asyncio.Lock (prevents parallel connect calls)
        self.voice_locks: dict[int, asyncio.Lock] = {}

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Automatically leaves the voice channel when the bot is the only one left."""
        voice_client = member.guild.voice_client
        if not voice_client:
            return

        # Check if the channel the bot is in has any non-bot members
        channel = voice_client.channel
        if not any(not m.bot for m in channel.members):
            # No humans left!
            log.info(f"Leaving empty voice channel: {channel.name} in {member.guild.name}")
            self.queues[member.guild.id] = []
            self.current_playing[member.guild.id] = None
            await voice_client.disconnect()

    def get_queue(self, guild_id: int) -> list:
        return self.queues.setdefault(guild_id, [])

    # ── Voice helpers ──────────────────────────────────────────────────────────

    async def ensure_voice(self, ctx: commands.Context) -> bool:
        """
        Makes sure the bot is connected to the author's voice channel.
        Returns True on success, False on failure.
        """
        if ctx.guild.id not in self.voice_locks:
            self.voice_locks[ctx.guild.id] = asyncio.Lock()

        async with self.voice_locks[ctx.guild.id]:
            # Already good
            if ctx.voice_client and ctx.voice_client.is_connected():
                return True

            if not ctx.author.voice:
                await ctx.send("❌ You need to join a voice channel first.")
                return False

            channel = ctx.author.voice.channel

            # Clean up any ghost state
            if ctx.voice_client:
                try:
                    await ctx.voice_client.disconnect(force=True)
                except Exception:
                    pass
                # Tell Discord gateway to clear the voice state
                await ctx.guild.change_voice_state(channel=None)
                await asyncio.sleep(0.5)

            try:
                await channel.connect(timeout=20.0, reconnect=True)
                log.info(f"Connected to voice channel: {channel.name}")
                return True
            except discord.ClientException as e:
                if "Already connected" in str(e):
                    # Gateway race — force-clear and retry once
                    await ctx.guild.change_voice_state(channel=None)
                    await asyncio.sleep(1.0)
                    try:
                        await channel.connect(timeout=20.0, reconnect=True)
                        return True
                    except Exception as e2:
                        await ctx.send(f"❌ Could not connect after reset: `{e2}`")
                        return False
                await ctx.send(f"❌ Voice connection error: `{e}`")
                return False
            except asyncio.TimeoutError:
                await ctx.send("❌ Timed out trying to connect to the voice channel.")
                return False
            except Exception as e:
                await ctx.send(f"❌ Unexpected error: `{e}`")
                return False

    # ── Queue / Playback engine ────────────────────────────────────────────────

    def _schedule_next(self, ctx: commands.Context, error=None):
        """Called by discord.py after a track ends (runs in non-async context)."""
        if error:
            log.error(f"Playback error: {error}")
        fut = asyncio.run_coroutine_threadsafe(self._play_next(ctx), self.bot.loop)
        try:
            fut.result(timeout=30)
        except Exception as e:
            log.error(f"Error scheduling next track: {e}")

    async def _play_next(self, ctx: commands.Context):
        """Pops the next search query from the queue and plays it."""
        queue = self.get_queue(ctx.guild.id)

        if not queue:
            # Queue empty — disconnect after a short delay
            self.current_playing[ctx.guild.id] = None
            await asyncio.sleep(1)
            if ctx.voice_client and not ctx.voice_client.is_playing():
                await ctx.voice_client.disconnect()
            return

        if not ctx.voice_client or not ctx.voice_client.is_connected():
            log.warning("Voice client gone before playing next track.")
            return

        search = queue.pop(0)

        async with ctx.typing():
            player = await YTDLSource.from_search(search, loop=self.bot.loop)

        if player is None:
            await ctx.send(f"❌ Could not load **{search}** — skipping.")
            await self._play_next(ctx)
            return

        self.current_playing[ctx.guild.id] = player

        try:
            ctx.voice_client.play(
                player,
                after=lambda e: self._schedule_next(ctx, e)
            )
        except discord.ClientException as e:
            log.error(f"play() error: {e}")
            await ctx.send(f"❌ Playback error: `{e}`")
            return

        embed = discord.Embed(
            title="🎶 Now Playing",
            description=f"**{player.title}**",
            color=discord.Color.blue()
        )
        if player.thumbnail:
            embed.set_thumbnail(url=player.thumbnail)
        if player.duration:
            mins, secs = divmod(int(player.duration), 60)
            embed.set_footer(text=f"Duration: {mins}:{secs:02d}")
        await ctx.send(embed=embed)

    # ── Commands ───────────────────────────────────────────────────────────────

    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx: commands.Context, *, search: str):
        """Search and play a song (or add to queue)."""
        if not await self.ensure_voice(ctx):
            return

        queue = self.get_queue(ctx.guild.id)
        queue.append(search)

        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            await ctx.send(f"📋 Added **{search}** to the queue. (Position: {len(queue)})")
        else:
            await self._play_next(ctx)

    @commands.command(name="lofi", aliases=["chill", "study"])
    async def lofi(self, ctx: commands.Context):
        """Instantly play 24/7 Lo-Fi radio for chilling."""
        LOFI_URL = "https://www.youtube.com/watch?v=jfKfPfyJRdk" # Lofi Girl - lofi hip hop radio
        if not await self.ensure_voice(ctx):
            return
        
        # Clear queue and stop current to play Lo-Fi immediately
        self.queues[ctx.guild.id] = [LOFI_URL]
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
        else:
            await self._play_next(ctx)
        
        await ctx.send("🍵 **Chill Mode: ON.** Playing 24/7 Lo-Fi Radio...")

    @commands.command(name="skip", aliases=["s"])
    async def skip(self, ctx: commands.Context):
        """Skips the current song."""
        if not ctx.voice_client or not (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            return await ctx.send("❌ Nothing is playing.")
        ctx.voice_client.stop()
        await ctx.send("⏭️ Skipped.")

    @commands.command(name="pause")
    async def pause(self, ctx: commands.Context):
        """Pauses the current song."""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("⏸️ Paused.")
        else:
            await ctx.send("❌ Nothing is playing.")

    @commands.command(name="resume")
    async def resume(self, ctx: commands.Context):
        """Resumes a paused song."""
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("▶️ Resumed.")
        else:
            await ctx.send("❌ Nothing is paused.")

    @commands.command(name="stop", aliases=["leave"])
    async def stop(self, ctx: commands.Context):
        """Clears the queue and disconnects the bot."""
        if ctx.voice_client:
            self.queues[ctx.guild.id] = []
            self.current_playing[ctx.guild.id] = None
            await ctx.voice_client.disconnect()
            await ctx.send("⏹️ Stopped and left the channel.")
        else:
            await ctx.send("❌ Not in a voice channel.")

    @commands.command(name="volume", aliases=["vol"])
    async def volume(self, ctx: commands.Context, volume: int):
        """Set the volume (1–100)."""
        if not ctx.voice_client or not ctx.voice_client.source:
            return await ctx.send("❌ Nothing is playing.")
        if not 1 <= volume <= 100:
            return await ctx.send("❌ Volume must be between 1 and 100.")
        ctx.voice_client.source.volume = volume / 100.0
        await ctx.send(f"🔊 Volume set to **{volume}%**.")

    @commands.command(name="queue", aliases=["q"])
    async def queue_cmd(self, ctx: commands.Context):
        """Shows the current queue."""
        queue = self.get_queue(ctx.guild.id)
        current = self.current_playing.get(ctx.guild.id)

        if not queue and not current:
            return await ctx.send("📭 Queue is empty.")

        embed = discord.Embed(title="🎶 Music Queue", color=discord.Color.blue())

        if current and ctx.voice_client and ctx.voice_client.is_playing():
            embed.add_field(name="▶️ Now Playing", value=current.title, inline=False)

        if queue:
            lines = "\n".join(f"**{i+1}.** {s}" for i, s in enumerate(queue[:10]))
            if len(queue) > 10:
                lines += f"\n*...and {len(queue)-10} more.*"
            embed.add_field(name="📋 Up Next", value=lines, inline=False)

        await ctx.send(embed=embed)

    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying(self, ctx: commands.Context):
        """Shows what is currently playing."""
        player = self.current_playing.get(ctx.guild.id)
        if not player or not ctx.voice_client or not ctx.voice_client.is_playing():
            return await ctx.send("❌ Nothing is currently playing.")
        embed = discord.Embed(
            title="🎶 Now Playing",
            description=f"**{player.title}**",
            color=discord.Color.blue()
        )
        if player.thumbnail:
            embed.set_thumbnail(url=player.thumbnail)
        await ctx.send(embed=embed)

    @commands.command(name="clearqueue", aliases=["cq"])
    async def clearqueue(self, ctx: commands.Context):
        """Clears all upcoming songs from the queue."""
        self.queues[ctx.guild.id] = []
        await ctx.send("🗑️ Queue cleared.")

    @commands.command(name="remove", aliases=["rm"])
    async def remove(self, ctx: commands.Context, index: int):
        """Removes a song from the queue by its position number."""
        queue = self.get_queue(ctx.guild.id)
        if index < 1 or index > len(queue):
            return await ctx.send(f"❌ Invalid position. Queue has {len(queue)} song(s).")
        removed = queue.pop(index - 1)
        await ctx.send(f"🗑️ Removed **{removed}** from position {index}.")


async def setup(bot):
    await bot.add_cog(Music(bot))
