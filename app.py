import discord
import logging
from os import getenv

# import dotenv
# dotenv.load_dotenv()


## Initialization
logger = logging.getLogger('discord')
logger.name = 'discord.bot'
intents = discord.Intents.all()
intents.message_content = True
prefix = getenv('PREFIX', "$")
client = discord.Client(intents=intents)

## Functions
async def helper(message):
    embed_all = discord.Embed(title='Help for all', description='List of commands are:', color=0x00ff00)
    embed_all.add_field(name=f'{prefix}help', value='Returns this message', inline=False)
    embed_all.add_field(name=f'{prefix}ping', value='Returns the latency of the bot', inline=False)
    embed_admin = discord.Embed(title='Help for admin', description='List of admin commands are:', color=0x00ff00)
    embed_admin.add_field(name=f'{prefix}purge n', value='Deletes the last n messages (max: 100)', inline=False)
    embed_admin.add_field(name=f'{prefix}kick @user1 @user2', value='Kicks list of users', inline=False)
    embed_admin.add_field(name=f'{prefix}reactrole :emoji1: @role1 :emoji2: @role2', value='Creates a react for role message', inline=False)
    await message.channel.send(embed=embed_all)
    await message.author.send(embed=embed_admin)

async def purge(message):
    try:
        n = int(message.content.split()[1])
        if not message.author.guild_permissions.manage_messages or not message.author.guild_permissions.administrator:
            await message.channel.send('You do not have permission to delete messages, incident reported.')
            logging.warning(f'{message.author.name} tried to delete messages in {message.guild.name}/{message.channel.name}')
            return
        if n > 100:
            await message.channel.send('Cannot delete more than 100 messages')
        else:
            await message.channel.purge(limit=n+1)
            logging.info(f'{n} messages deleted in {message.guild.name}/{message.channel.name} by {message.author.name}')
    except Exception as e:
        if "403" in str(e):
            await message.channel.send('Unable to delete messages, missing permissions.')
        else:
            await message.channel.send(f'Failed to delete messages, check logs for more info')

async def kick(message):
    try:
        if not message.author.guild_permissions.kick_members or not message.author.guild_permissions.administrator:
            await message.channel.send('You do not have permission to kick members, incident reported.')
            logging.warning(f'{message.author.name} tried to kick members in {message.guild.name}/{message.channel.name}')
            return
        else:
            for member in message.mentions:
                await member.kick()
                logging.info(f'{member.name} kicked from {message.guild.name}/{message.channel.name} by {message.author.name}')
    except Exception as e:
        if "403" in str(e):
            await message.channel.send('Unable to kick members, missing permissions.')
        else:
            await message.channel.send(f'Failed to kick members, check logs for more info')

async def reactrole(message):
    if not message.author.guild_permissions.manage_roles or not message.author.guild_permissions.administrator:
        await message.channel.send('You do not have permission to create reactroles, incident reported.')
        logging.warning(f'{message.author.name} tried to create reactrole in {message.guild.name}/{message.channel.name}')
        return
    sequence = message.content.split()[1:]
    if len(sequence) % 2 != 0:
        await message.channel.send('Invalid sequence')
        return
    try:
        embed = discord.Embed(title='React Role', description='React to this message to get a role', color=0x00ff00)
        for i in range(0, len(sequence), 2):
            embed.add_field(name=sequence[i], value=sequence[i+1], inline=False)
        msg = await message.channel.send(embed=embed)
        for i in range(0, len(sequence), 2):
            await msg.add_reaction(sequence[i])
        await message.delete()
    except Exception as e:
        if "403" in str(e):
            await message.channel.send('Unable to add reactions, missing permissions.')
        else:
            await message.channel.send(f'Failed to add reactions, check logs for more info')

async def message_handler(message):
    message_content = message.content.lower()
    if message_content.startswith(prefix + 'help'):
        await helper(message)
    elif message_content.startswith(prefix + 'ping'):
        await message.channel.send(f'🏓 Pong! `{round(client.latency * 1000)}ms`')
    elif message_content.startswith(prefix + 'purge'):
        await purge(message)
    elif message_content.startswith(prefix + 'kick'):
        await kick(message)
    elif message_content.startswith(prefix + 'reactrole'):
        await reactrole(message)

def get_role_from_id(guild, role_id):
        for role in guild.roles:
            logger.debug(f'{role.name} {role.id} | {role_id}')
            if role_id == str(role.id):
                logger.debug(f'Found role: {role.name}')
                return role

## Events
@client.event
async def on_ready():
    logger.info(f'Logged in successfully as: {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    await message_handler(message)

@client.event
async def on_raw_reaction_add(payload):
    if payload.member.bot or payload.user_id == client.user.id:
        return
    channel = client.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    if not message.author.id == client.user.id and not message.embeds:
        return
    for reaction in message.reactions:
        if reaction.emoji == payload.emoji.name or reaction.emoji.id == payload.emoji.id:
            role = reaction.message.embeds[0].fields[reaction.message.reactions.index(reaction)].value.replace('<@&', '').replace('>', '')
            role = get_role_from_id(message.guild, role)
            await payload.member.add_roles(role)
            return
    await reaction.remove(payload.member)

@client.event
async def on_raw_reaction_remove(payload):
    if payload.user_id == client.user.id:
        return
    channel = client.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)
    if not message.author.id == client.user.id and not message.embeds:
        return
    for reaction in message.reactions:
        if reaction.emoji == payload.emoji.name or reaction.emoji.id == payload.emoji.id:
            role = reaction.message.embeds[0].fields[reaction.message.reactions.index(reaction)].value.replace('<@&', '').replace('>', '')
            role = get_role_from_id(message.guild, role)
            member = discord.utils.get(message.guild.members, id=payload.user_id)
            await member.remove_roles(role)


## Main
client.run(getenv('TOKEN'))