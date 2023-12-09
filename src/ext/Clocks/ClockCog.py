import logging
from discord.ext import commands
from discord import Embed, File, ApplicationContext, PartialEmoji, Interaction, ButtonStyle as Bstyle, \
    InteractionResponded
from discord.ui import button, View, Button

from .clocks import NoClockImageException, load_clock_files, save_clocks, Clock, load_clocks, get_clock_image
from ..ContextInfo import ContextInfo, initContext
from ... import GlobalVariables as global_vars

logger = logging.getLogger('bot')

MESSAGE_DELETION_DELAY: int = 10
BUTTON_VIEW_TIMEOUT: int = 21600  # 6 hours

# TODO use this error message everywhere in the code where the user gets a unknown error/interaction failed
error_message = "An error has occurred. Try re-inviting the bot to your server through the button in its description, " \
                "the issue may be due to updated required permissions. Sorry for the inconvenience\n" \
                "If the issue persists even after a re-invite, please send my creator an error message with a screenshot and describe your problem.\n" \
                "**Use the discord linked in the \\help command.\n**" \
                "Error:\n"


# This will be deprecated in a future update of py-cord, which introduces interaction.respond and interaction.edit
# I'm making my own shorthand since I haven't yet figured out how to get access to that code
async def edit_interaction_message(interaction: Interaction, params: dict):
    try:
        if not interaction.response.is_done():
            await interaction.response.edit_message(**params)
            return await interaction.original_response()
        else:
            return await interaction.edit_original_response(**params)
    except InteractionResponded:
        return await interaction.edit_original_response(**params)


class ClockAdjustmentView(View):
    def __init__(self, clock_tag: str, associated_user: str, channel_message_id: tuple[int, int] = None):
        super().__init__(timeout=BUTTON_VIEW_TIMEOUT)
        self.clock_tag = clock_tag
        self.associated_user = associated_user
        self.channel_message_id = channel_message_id
        logger.debug("ClockAdjustmentView created: [clock_tag={0}, associated_user={1}, channel_message_id={2}]"
                     .format(self.clock_tag, self.associated_user, self.channel_message_id))
        logger.debug(f"type associated user: {type(self.associated_user)}")

    def log_view_interaction(self, interaction_name: str, interaction: Interaction):
        logger.debug("{0} called: [interaction ID={1}, clock_tag={2}, associated_user={3}, channel_message_id={4}]"
                     .format(interaction_name, interaction.user.id, self.clock_tag, self.associated_user, self.channel_message_id))
        logger.debug(f"type associated user: {type(self.associated_user)}")

    async def on_timeout(self) -> None:
        self.update_channel_message_id()
        message = await self.get_message()
        if message is not None:
            await(
                message
            ).edit(view=LockedClockAdjustmentView(self.clock_tag, self.associated_user, self.channel_message_id))
        global_vars.bot.add_view(LockedClockAdjustmentView("", ""))
        self.stop()

    def update_channel_message_id(self):
        if self.message:
            self.channel_message_id = (self.message.channel.id, self.message.id)

    def refresh_clock_data(self, interaction: Interaction):
        self.clock_tag = interaction.message.embeds[0].description.split(":")[1].strip().replace("_", "")
        self.associated_user = str(interaction.message.interaction.data['user']['id'])

    async def get_message(self):
        if self.message:
            return self.message
        elif self.channel_message_id is not None:
            return await (
                    await global_vars.bot.fetch_channel(self.channel_message_id[0])
                ).fetch_message(self.channel_message_id[1])
        else:
            return None

    @button(label="tick", style=Bstyle.grey, row=0, emoji=PartialEmoji.from_str("▶"), custom_id="plus_tick_button")
    async def button_tick_callback(self, _: Button, interaction: Interaction):
        self.log_view_interaction("tick", interaction)
        ctx: ContextInfo = await initContext(interaction=interaction)
        try:
            params: dict = tick_clock_logic(clock_tag=self.clock_tag, executing_user=self.associated_user, ticks=1)
            await edit_interaction_message(interaction, params)
        except Exception as e:
            logger.error(e)
            await ctx.respond(error_message +
                              str(e))

    @button(label="back_tick", style=Bstyle.grey, row=0, emoji=PartialEmoji.from_str("◀"), custom_id="minus_tick_button")
    async def button_back_tick_callback(self, _: Button, interaction: Interaction):
        self.log_view_interaction("back_tick", interaction)
        ctx: ContextInfo = await initContext(interaction=interaction)
        try:
            params: dict = tick_clock_logic(clock_tag=self.clock_tag, executing_user=self.associated_user, ticks=-1)
            await edit_interaction_message(interaction, params)
        except Exception as e:
            logger.error(e)
            await ctx.respond(error_message +
                              str(e))

    @button(label="delete", style=Bstyle.grey, row=0, emoji=PartialEmoji.from_str("🚮"), custom_id="delete_button")
    async def button_delete_callback(self, _: Button, interaction: Interaction):
        self.log_view_interaction("delete", interaction)
        ctx: ContextInfo = await initContext(interaction=interaction)
        try:
            await remove_clock_command_logic(ctx, clock_tag=self.clock_tag, executing_user=self.associated_user)
            await interaction.message.delete()
        except Exception as e:
            logger.error(e)
            await ctx.respond(error_message +
                              str(e))

    @button(label="lock view", style=Bstyle.red, row=1, emoji=PartialEmoji.from_str("🔒"), custom_id="lock_view_button")
    async def button_lock_callback(self, _: Button, interaction: Interaction):
        self.log_view_interaction("lock view", interaction)
        ctx: ContextInfo = await initContext(interaction=interaction)
        try:
            self.refresh_clock_data(interaction)
            self.update_channel_message_id()
            await edit_interaction_message(
                interaction,
                {"view": LockedClockAdjustmentView(self.clock_tag, self.associated_user, self.channel_message_id)}
            )
            global_vars.bot.add_view(LockedClockAdjustmentView("", ""))
            self.stop()
        except Exception as e:
            logger.error(e)
            await ctx.respond(error_message +
                              str(e))


class LockedClockAdjustmentView(View):
    def __init__(self, clock_tag: str, associated_user: str, channel_message_id: tuple[int, int] = None):
        super().__init__(timeout=None)
        self.clock_tag = clock_tag
        self.associated_user = associated_user
        self.channel_message_id = channel_message_id
        logger.debug("LockedClockAdjustmentView created: [clock_tag={0}, associated_user={1}, channel_message_id={2}]"
                     .format(self.clock_tag, self.associated_user, self.channel_message_id))
        logger.debug(f"type associated user: {type(self.associated_user)}")

    def refresh_clock_data(self, interaction: Interaction):
        self.clock_tag = interaction.message.embeds[0].description.split(":")[1].strip().replace("_", "")
        self.associated_user = str(interaction.message.interaction.data['user']['id'])

    def log_view_interaction(self, interaction_name: str, interaction: Interaction):
        logger.debug("{0} called: [interaction ID={1}, clock_tag={2}, associated_user={3}, channel_message_id={4}]"
                     .format(interaction_name, interaction.user.id, self.clock_tag, self.associated_user, self.channel_message_id))
        logger.debug(f"type associated user: {type(self.associated_user)}")

    @button(label="unlock view", style=Bstyle.primary, row=0, emoji=PartialEmoji.from_str("🔓"), custom_id="unlock_clock_button")
    async def button_lock_callback(self, _: Button, interaction: Interaction):
        self.refresh_clock_data(interaction)
        if str(interaction.user.id) != self.associated_user:
            self.log_view_interaction("LockedClockAdjustmentView/unlock_view, not owner", interaction)
            await (await initContext(interaction=interaction)).respond("You are not the owner of this clock", delay=10)
            return
        if self.channel_message_id is None:
            self.log_view_interaction("LockedClockAdjustmentView/channel_message_id is None", interaction)
            self.channel_message_id = (interaction.channel.id, interaction.message.id)
        await edit_interaction_message(
            interaction,
            {"view": ClockAdjustmentView(self.clock_tag, self.associated_user, self.channel_message_id)}
        )
        global_vars.bot.add_view(LockedClockAdjustmentView("", ""))
        self.stop()


def get_clock_response_params(clock: Clock, assiciated_user: str) -> dict:
    embed = Embed(title=f'**{clock.name}**')
    params = {
        "file": None,
        "embed": embed,
        "view": ClockAdjustmentView(clock_tag=clock.tag, associated_user=assiciated_user)
    }
    try:
        image_file: File = get_clock_image(clock)
        embed.set_thumbnail(url=f'attachment://{image_file.filename}')
        params["file"] = image_file
        embed.description = f"_Tag: {clock.tag}_"
    except NoClockImageException:
        embed.set_footer(text="Clocks of this size don't have output images")
        embed.description = f'Tag: _{clock.tag}_ : {{{clock.ticks}/{clock.size}}}'
        logger.debug(
            f"clock of size {clock.size} was printed without image, make sure images are included for all sizes needed."
        )
    no_none_params = {k: v for k, v in params.items() if v is not None} # removes all parameters that are none

    return no_none_params


async def add_clock_command_logic(ctx: ContextInfo, clock_tag: str, clock_title: str, clock_size: int, clock_ticks: int = 0):
    executing_user = str(ctx.author.id)
    clock_tag = clock_tag.replace("_", "").strip().lower()
    clock_dic = load_clocks(executing_user)
    if len(clock_dic) == 40:
        await ctx.respond("You already have 40 clocks, please remove one.", delay=MESSAGE_DELETION_DELAY)
        return

    if clock_tag in clock_dic:
        response_data: dict = get_clock_response_params(clock_dic[clock_tag], executing_user)
        response_data["content"] = "This clock already exists!"
        await ctx.respond(**response_data)
    else:
        clock_dic[clock_tag] = Clock(clock_tag, clock_title, clock_size, clock_ticks)
        save_clocks(executing_user, clock_dic)
        await ctx.respond(**get_clock_response_params(clock_dic[clock_tag], executing_user))


async def remove_clock_command_logic(ctx: ContextInfo, clock_tag: str, executing_user: str = None):
    if executing_user is None:
        executing_user = str(ctx.author.id)
    elif type(executing_user) != str:
        logger.error(f"executing user is not a string")
        raise Exception("clock_removal, executing_user is not a string for some reason")
    clock_tag = clock_tag.strip().lower()
    clock_dic = load_clocks(executing_user)
    if clock_tag in clock_dic:
        del clock_dic[clock_tag]
        save_clocks(executing_user, clock_dic)
        await ctx.respond(content="The clock has been deleted!\n", delay=MESSAGE_DELETION_DELAY)
    else:
        await ctx.respond(f"Clock with this tag does not exist: {clock_tag}\n This shouldn't be possible, please contact the developer if this happens to you."
                          f"See the /help command")
        logger.error(f"The bot tried to remove a clock that does not exist for user: ({executing_user}), clock tag: ({clock_tag})")


async def show_clock_command_logic(ctx: ContextInfo, clock_tag: str, executing_user: str = None):
    if executing_user is None:
        executing_user = str(ctx.author.id)
    elif type(executing_user) != str:
        logger.error(f"executing user is not a string")
        raise Exception("clock_removal, executing_user is not a string for some reason")
    clock_tag = clock_tag.strip().lower()
    clock_dic = load_clocks(executing_user)
    if clock_tag in clock_dic:
        await ctx.respond(**get_clock_response_params(clock_dic[clock_tag], executing_user))
    else:
        await ctx.respond("This clock does not exist", delay=MESSAGE_DELETION_DELAY)


async def tick_clock_command_ctx(ctx: ContextInfo, clock_tag: str, ticks: int = 1, executing_user: str = None):
    """
    A shorthand async function, that calls both tick_clock_logic and responds via ContextInfo
    """
    if executing_user is None:
        executing_user = str(ctx.author.id)
    elif type(executing_user) != str:
        logger.error(f"executing user is not a string")
        raise Exception("clock_removal, executing_user is not a string for some reason")
    await ctx.respond(**tick_clock_logic(clock_tag, executing_user, ticks))


def tick_clock_logic(clock_tag: str, executing_user: str, ticks: int = 1) -> dict:
    """
    Logic for accessing the clocks of the executing user and ticking a specific clock by the assigned ticks.
    Includes access checks

    :return: a dictionary containing the paramaters that can be passed to a ContextInfo respond logic.
    """
    clock_tag = clock_tag.strip().lower()
    clock_dic = load_clocks(executing_user)
    clock = clock_dic.get(clock_tag)
    if clock:
        clock.tick(ticks)
        save_clocks(executing_user, clock_dic)
        return get_clock_response_params(clock, executing_user)
    else:
        logger.error(f"The bot tried to tick a clock that does not exist for user: ({executing_user}), clock tag: ({clock_tag})")
        return {"content": f"Clock with this tag does not exist: {clock_tag}\n Make sure to use the clock tag and not its name!", "delay": MESSAGE_DELETION_DELAY}


class ClockCog(commands.Cog):

    @commands.slash_command(name="clock_add", description="Adds a new clock of a certain size.")
    async def add_clock(self, ctx: ApplicationContext, clock_tag: str, clock_title: str, clock_size: int, clock_ticks: int = 0):
        await add_clock_command_logic(await initContext(ctx=ctx), clock_tag, clock_title, clock_size, clock_ticks)

    @commands.slash_command(name="clock", description="Prints a saved clock, with picture if possible")
    async def show_clock(self, ctx: ApplicationContext, clock_tag: str):
        await show_clock_command_logic(await initContext(ctx=ctx), clock_tag)

    @commands.slash_command(name="clock_all", description="Prints out all saved clocks")
    async def all_clocks(self, ctx: ApplicationContext):
        user_id = str(ctx.author.id)
        clock_dic = load_clocks(user_id)
        if len(clock_dic) == 0:
            await(await ctx.respond("You have no existing clock. use the **clock_add** command to create clocks.")).delete_original_response(delay=MESSAGE_DELETION_DELAY)
            return

        all_c = "These are the clocks that you have created:\n"
        for clock in clock_dic.values():
            all_c += str(clock) + "\n"
        await(await ctx.respond(all_c)).delete_original_response(delay=40)


def setup(bot: commands.Bot):
    # Every extension should have this function
    load_clock_files()
    bot.add_cog(ClockCog())
    logger.info("clock extension loaded")
