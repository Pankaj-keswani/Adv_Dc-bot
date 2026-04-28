import discord
from PIL import Image, ImageDraw, ImageFont, ImageOps
import aiohttp
import io
import os
from pathlib import Path

# Paths
BG_PATH = Path("data/welcome_bg.png")

def get_font_path(bold=False):
    # Windows paths
    win_font = "C:\\Windows\\Fonts\\arialbd.ttf" if bold else "C:\\Windows\\Fonts\\arial.ttf"
    if os.path.exists(win_font):
        return win_font
    
    # Linux / Docker paths (Hugging Face)
    linux_fonts = [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf"
    ]
    for f in linux_fonts:
        if os.path.exists(f):
            return f
    return None

FONT_PATH = get_font_path(bold=False)
FONT_BOLD_PATH = get_font_path(bold=True)

async def generate_welcome_image(member: discord.Member) -> io.BytesIO:
    """
    Generates a custom welcome image for a member.
    """
    # Create canvas or open background
    if BG_PATH.exists():
        img = Image.open(BG_PATH).convert("RGBA")
        # Resize if necessary to 1000x400
        img = img.resize((1000, 400), Image.LANCZOS)
    else:
        # Fallback to a dark gradient background if file missing
        img = Image.new("RGBA", (1000, 400), (20, 20, 25, 255))

    draw = ImageDraw.Draw(img)

    # 1. Load Avatar
    avatar_url = member.display_avatar.with_format("png").url
    async with aiohttp.ClientSession() as session:
        async with session.get(avatar_url) as resp:
            if resp.status == 200:
                avatar_bytes = await resp.read()
                avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            else:
                # Fallback to empty image if avatar fail
                avatar_img = Image.new("RGBA", (200, 200), (128, 128, 128, 255))

    # 2. Process Avatar (Circle Crop)
    avatar_size = 180
    avatar_img = avatar_img.resize((avatar_size, avatar_size), Image.LANCZOS)
    
    mask = Image.new("L", (avatar_size, avatar_size), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse((0, 0, avatar_size, avatar_size), fill=255)
    
    # Optional: White Border
    border_size = 6
    border_img = Image.new("RGBA", (avatar_size + border_size*2, avatar_size + border_size*2), (0, 0, 0, 0))
    draw_border = ImageDraw.Draw(border_img)
    draw_border.ellipse((0, 0, avatar_size + border_size*2, avatar_size + border_size*2), outline=(255, 255, 255, 255), width=border_size)

    # 3. Paste Avatar onto Background
    avatar_x = 50
    avatar_y = (400 - avatar_size) // 2
    
    img.paste(border_img, (avatar_x - border_size, avatar_y - border_size), border_img)
    img.paste(avatar_img, (avatar_x, avatar_y), mask)

    # 4. Add Text
    try:
        font_main = ImageFont.truetype(FONT_BOLD_PATH, 55)
        font_sub = ImageFont.truetype(FONT_PATH, 35)
        font_member = ImageFont.truetype(FONT_PATH, 28)
    except:
        # Fallback to default if font missing
        font_main = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_member = ImageFont.load_default()

    text_x = avatar_x + avatar_size + 40
    
    # Welcome Text
    draw.text((text_x, 110), f"WELCOME TO THE SERVER", font=font_sub, fill=(255, 255, 255, 200))
    
    # User Name
    user_name = f"{member.name}"
    draw.text((text_x, 150), user_name, font=font_main, fill=(255, 255, 255, 255))
    
    # Member Count
    member_count = f"Member #{member.guild.member_count}"
    draw.text((text_x, 230), member_count, font=font_member, fill=(100, 200, 255, 255))

    # 5. Export to Bytes
    output = io.BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output
