import discord
from discord.ext import commands
from loguru import logger

from prisma.enums import CaseType
from prisma.models import Case
from tux.utils import checks
from tux.utils.constants import Constants as CONST

from . import ModerationCogBase


class SBan(ModerationCogBase):
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(bot)

    async def check_sban_conditions(
        self,
        ctx: commands.Context[commands.Bot],
        target: discord.Member,
        moderator: discord.Member,
    ) -> bool:
        if ctx.guild is None:
            logger.warning("Ban command used outside of a guild context.")
            return False

        if target == ctx.author:
            await ctx.send("You cannot snippet ban yourself.", delete_after=30, ephemeral=True)
            return False

        if target.top_role >= moderator.top_role:
            await ctx.send(
                "You cannot snippet ban a user with a higher or equal role.",
                delete_after=30,
                ephemeral=True,
            )
            return False

        if target == ctx.guild.owner:
            await ctx.send("You cannot snippet ban the server owner.", delete_after=30, ephemeral=True)
            return False

        return True

    @commands.hybrid_command(
        name="sban",
        aliases=["sb"],
        usage="$sban [target]",
    )
    @commands.guild_only()
    @checks.has_pl(3)
    async def sban(
        self,
        ctx: commands.Context[commands.Bot],
        target: discord.Member,
        *,
        reason: str,
    ) -> None:
        """
        Ban a user from the server.

        Parameters
        ----------
        ctx : commands.Context[commands.Bot]
            The context in which the command is being invoked.
        target : discord.Member
            The member to ban.
        flags : BanFlags
            The flags for the command. (reason: str, purge_days: int, silent: bool)

        Raises
        ------
        discord.Forbidden
            If the bot is unable to ban the user.
        discord.HTTPException
            If an error occurs while banning the user.
        """
        if ctx.guild is None:
            logger.warning("Ban command used outside of a guild context.")
            return

        moderator = await commands.MemberConverter().convert(ctx, str(ctx.author.id))

        if not await self.check_sban_conditions(ctx, target, moderator):
            return

        case = await self.db.case.insert_case(
            case_target_id=target.id,
            case_moderator_id=ctx.author.id,
            case_type=CaseType.SNIPPETBAN,
            case_reason=reason,
            guild_id=ctx.guild.id,
        )

        await self.handle_case_response(ctx, case, "created", reason, target)

    async def handle_case_response(
        self,
        ctx: commands.Context[commands.Bot],
        case: Case | None,
        action: str,
        reason: str,
        target: discord.Member | discord.User,
        previous_reason: str | None = None,
    ) -> None:
        moderator = ctx.author

        fields = [
            ("Moderator", f"__{moderator}__\n`{moderator.id}`", True),
            ("Target", f"__{target}__\n`{target.id}`", True),
            ("Reason", f"> {reason}", False),
        ]

        if previous_reason:
            fields.append(("Previous Reason", f"> {previous_reason}", False))

        if case is not None:
            embed = await self.create_embed(
                ctx,
                title=f"Case #{case.case_number} ({case.case_type}) {action}",
                fields=fields,
                color=CONST.EMBED_COLORS["CASE"],
                icon_url=CONST.EMBED_ICONS["ACTIVE_CASE"],
            )
            embed.set_thumbnail(url=target.avatar)
        else:
            embed = await self.create_embed(
                ctx,
                title=f"Case {action} ({CaseType.BAN})",
                fields=fields,
                color=CONST.EMBED_COLORS["CASE"],
                icon_url=CONST.EMBED_ICONS["ACTIVE_CASE"],
            )

        await self.send_embed(ctx, embed, log_type="mod")
        await ctx.send(embed=embed, delete_after=30, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SBan(bot))
