import discord
from discord.ext import commands
from loguru import logger

from prisma.enums import CaseType
from tux.utils import checks
from tux.utils.flags import JailFlags, generate_usage

from . import ModerationCogBase


class Jail(ModerationCogBase):
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__(bot)
        self.jail.usage = generate_usage(self.jail, JailFlags)

    @commands.hybrid_command(
        name="jail",
        aliases=["j"],
    )
    @commands.guild_only()
    @checks.has_pl(2)
    async def jail(
        self,
        ctx: commands.Context[commands.Bot],
        member: discord.Member,
        *,
        flags: JailFlags,
    ) -> None:
        """
        Jail a user in the server.

        Parameters
        ----------
        ctx : commands.Context[commands.Bot]
            The discord context object.
        member : discord.Member
            The member to jail.
        flags : JailFlags
            The flags for the command. (reason: str, silent: bool)
        """

        if not ctx.guild:
            logger.warning("Jail command used outside of a guild context.")
            return

        moderator = ctx.author

        if not await self.check_conditions(ctx, member, moderator, "jail"):
            return

        is_valid, jail_role, jail_channel = await self.check_jail_conditions(ctx, member)
        if not is_valid:
            return
        assert jail_role is not None
        assert jail_channel is not None

        user_roles: list[discord.Role] = self._get_manageable_roles(member, jail_role)
        case_user_roles = [role.id for role in user_roles]

        try:
            case = await self.db.case.insert_case(
                case_user_id=member.id,
                case_moderator_id=ctx.author.id,
                case_type=CaseType.JAIL,
                case_reason=flags.reason,
                guild_id=ctx.guild.id,
                case_user_roles=case_user_roles,
            )

        except Exception as e:
            logger.error(f"Failed to jail {member}. {e}")
            await ctx.send(f"Failed to jail {member}. {e}", delete_after=30, ephemeral=True)
            return

        try:
            if user_roles:
                await member.remove_roles(*user_roles, reason=flags.reason, atomic=False)
                await member.add_roles(jail_role, reason=flags.reason)

        except (discord.Forbidden, discord.HTTPException) as e:
            logger.error(f"Failed to jail {member}. {e}")
            await ctx.send(f"Failed to jail {member}. {e}", delete_after=30, ephemeral=True)
            return

        await self.send_dm(ctx, flags.silent, member, flags.reason, "jailed")
        await self.handle_case_response(ctx, CaseType.JAIL, case.case_number, flags.reason, member)

    def _get_manageable_roles(
        self,
        member: discord.Member,
        jail_role: discord.Role,
    ) -> list[discord.Role]:
        """
        Get the roles that can be managed by the bot.

        Parameters
        ----------
        member : discord.Member
            The member to jail.
        jail_role : discord.Role
            The jail role.

        Returns
        -------
        list[discord.Role]
            The roles that can be managed by the bot.
        """

        return [
            role
            for role in member.roles
            if not (
                role.is_bot_managed()
                or role.is_premium_subscriber()
                or role.is_integration()
                or role.is_default()
                or role == jail_role
            )
            and role.is_assignable()
        ]


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Jail(bot))
