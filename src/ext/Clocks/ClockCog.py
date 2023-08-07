import asyncio
import logging
from functools import wraps

import decohints
from discord.ext import commands
from discord import Embed, File, ApplicationContext, PartialEmoji, Interaction, ButtonStyle as Bstyle
from discord.ui import button, View, Button

from .clocks import NoClockImageException, load_clock_files, save_clocks, Clock, load_clocks, get_clock_image
from ..ContextInfo import ContextInfo, initContext


logger = logging.getLogger('bot')


class ClockAdjustmentView(View):
    def __init__(self, clock_tag: str, user_id: str):
        super().__init__(timeout=600)
        self.clock_tag = clock_tag
        self.user_id = user_id

    @button(label="tick", style=Bstyle.grey, row=0, emoji=PartialEmoji.from_str("▶"))
    async def button_callback(self, _: Button, interaction: Interaction):
        await interaction.message.delete()
        await tick_clock_logic(await initContext(interaction=interaction), clock_tag=self.clock_tag, executing_user=self.user_id)

    @button(label="back_tick", style=Bstyle.grey, row=0, emoji=PartialEmoji.from_str("◀"))
    async def button_callback1(self, _: Button, interaction: Interaction):
        await interaction.message.delete()
        await tick_clock_logic(await initContext(interaction=interaction), clock_tag=self.clock_tag, ticks=-1, executing_user=self.user_id)

    @button(label="delete", style=Bstyle.grey, row=0, emoji=PartialEmoji.from_str("🚮"))
    async def button_callback2(self, _: Button, interaction: Interaction):
        await interaction.message.delete()
        await remove_logic(await initContext(interaction=interaction), clock_tag=self.clock_tag, executing_user=self.user_id)


async def print_clock(ctx: ContextInfo, clock: Clock, executing_user:str = None):
    embed = Embed(title=f'**{clock.name}**')
    if executing_user is None:
        executing_user = str(ctx.author.id)
    try:

        image_file: File = get_clock_image(clock)
        embed.set_thumbnail(url=f'attachment://{image_file.filename}')
        embed.description = f"_Tag: {clock.tag}_"
        await ctx.respond(embed=embed, file=image_file, view=ClockAdjustmentView(clock_tag=clock.tag, user_id=executing_user))
    except NoClockImageException:
        embed.set_footer(text="Clocks of this size don't have output images")
        embed.description = str(clock)
        await ctx.respond(embed=embed, view=ClockAdjustmentView(clock_tag=clock.tag, user_id=executing_user))
        logger.debug(
            f"clock of size {clock.size} was printed without image, make sure images are included for all sizes needed."
        )


async def add_logic(ctx: ContextInfo, clock_tag: str, clock_title: str, clock_size: int, clock_ticks: int = 0):
    user_id = str(ctx.author.id)
    clock_tag = clock_tag.strip().lower()
    clock_dic = load_clocks(user_id)
    if len(clock_dic) == 40:
        await ctx.respond("You already have 40 clocks, please remove one.")
        return

    if clock_tag in clock_dic:
        await ctx.respond(content="This clock already exists!", delay=5)
        await print_clock(ctx, clock_dic[clock_tag])
    else:
        clock_dic[clock_tag] = Clock(clock_tag, clock_title, clock_size, clock_ticks)
        save_clocks(user_id, clock_dic)
        await ctx.respond("Clock created", delay=5)
        await print_clock(ctx, clock_dic[clock_tag])


async def remove_logic(ctx: ContextInfo, clock_tag: str, executing_user: str = None):
    if executing_user is None:
        executing_user = str(ctx.author.id)
    clock_tag = clock_tag.strip().lower()
    clock_dic = load_clocks(executing_user)
    if clock_tag in clock_dic:
        del clock_dic[clock_tag]
        save_clocks(executing_user, clock_dic)
        await ctx.respond(content="The clock has been deleted!\n", delay=5)
    else:
        await ctx.respond(f"Clock with this tag does not exist: {clock_tag}\nMake sure to use the clock tag and not its name!", delay=5)


async def show_clock_logic(ctx: ContextInfo, clock_tag: str, executing_user: str = None):
    if executing_user is None:
        executing_user = str(ctx.author.id)
    clock_tag = clock_tag.strip().lower()
    clock_dic = load_clocks(executing_user)
    if clock_tag in clock_dic:
        await print_clock(ctx, clock_dic[clock_tag])
    else:
        await ctx.respond("This clock does not exist", delay=5)


async def tick_clock_logic(ctx: ContextInfo, clock_tag: str, ticks: int = 1, executing_user: str = None):
    if executing_user is None:
        executing_user = str(ctx.author.id)
    clock_tag = clock_tag.strip().lower()
    clock_dic = load_clocks(executing_user)
    clock = clock_dic.get(clock_tag)
    if clock:
        clock.tick(ticks)
        save_clocks(executing_user, clock_dic)
        await print_clock(ctx, clock, executing_user)
    else:
        await ctx.respond(f"Clock with this tag does not exist: {clock_tag}\n Make sure to use the clock tag and not its name!", delay=5)


class ClockCog(commands.Cog):

    @commands.slash_command(name="clock_add", description="Adds a new clock of a certain size.")
    async def add_clock(self, ctx: ApplicationContext, clock_tag: str, clock_title: str, clock_size: int, clock_ticks: int = 0):
        await add_logic(await initContext(ctx=ctx), clock_tag, clock_title, clock_size, clock_ticks)

    @commands.slash_command(name="clock", description="Prints a saved clock, with picture if possible")
    async def show_clock(self, ctx: ApplicationContext, clock_tag: str):
        await show_clock_logic(await initContext(ctx=ctx), clock_tag)

    @commands.slash_command(name="clock_all", description="Prints out all saved clocks")
    async def all_clocks(self, ctx: ApplicationContext):
        user_id = str(ctx.author.id)
        clock_dic = load_clocks(user_id)
        if len(clock_dic) == 0:
            await(await ctx.respond("You have no existing clock. use the **clock_add** command to create clocks.")).delete_original_response(delay=10)
            return

        all_c = "These are the clocks that you have created:\n"
        for clock in clock_dic.values():
            all_c += str(clock) + "\n"
        await(await ctx.respond(all_c)).delete_original_response(delay=10)


def setup(bot: commands.Bot):
    # Every extension should have this function
    load_clock_files()
    bot.add_cog(ClockCog())
    logger.info("clock extension loaded\n")
