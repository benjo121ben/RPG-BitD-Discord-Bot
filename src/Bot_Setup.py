from discord.ext import commands
from src import GlobalVariables, command_helper_functions as hlp_f


ext_base_path = "src.ext."


def start_bot(_command_prefix, _bot_token):
    GlobalVariables.bot = commands.Bot(_command_prefix)
    load_extensions(GlobalVariables.bot)

    @GlobalVariables.bot.event
    async def on_ready():
        print("Bot startup completed")
        print('We have logged in as {0.user}'.format(GlobalVariables.bot))

    @GlobalVariables.bot.command(name="r")
    async def reload(ctx):
        if not hlp_f.check_admin(ctx):
            await ctx.send("you are not authorized to use this command")
            return
        load_extensions(GlobalVariables.bot, reload=True)
        await ctx.send("reloaded")

    print("starting up bot")
    GlobalVariables.bot.run(_bot_token)


def load_extensions(_bot, reload=False):
    def load_ext(extension):
        if reload:
            _bot.reload_extension(ext_base_path + extension)
        else:
            _bot.load_extension(ext_base_path + extension)

    print("\n---------------------LOADING EXTENSIONS---------------------\n")
    load_ext("Campaign.campaign_commands")
    load_ext("Clocks.clock_commands")
    load_ext("Entangle_DevilsBargains.Ent_DB_commands")
    print("---------------------EXTENSIONS LOADED---------------------")
    print()

