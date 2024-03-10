# Dependencies
import logging
import docker
from docker.models.containers import Container


# Logging
logger = logging.getLogger('discord')


# Functions
async def mc_restart(message) -> None:
    if message.author.guild_permissions.administrator:
        client: docker.DockerClient = docker.from_env()
        container: Container = client.containers.get('mc-modded')
        await message.channel.send('Restarting minecraft server...')
        logging.info(f'Minecraft server restart attempt by {message.author.name} in {message.guild.name}/{message.channel.name}')
        try:
            container.restart()
        except Exception as e:
            logging.warning(f'Minecraft server restart failed: {e}')
            await message.channel.send(f':x: Failed to update server, please contact administrator')
        else:
            await message.channel.send(f':white_check_mark: Server restarted')
    else:
        await message.channel.send('You do not have permission to restart servers, incident reported.')
        logging.warning(f'{message.author.name} tried to restart servers in {message.guild.name}/{message.channel.name}')
