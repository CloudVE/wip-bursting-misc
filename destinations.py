import os
import cachetools

from galaxy.jobs import JobDestination

from cloudlaunch_cli.api.client import APIClient


# Global variable for tracking round-robin index
current_server_index = 0


def _get_cloudlaunch_client(app):
    # Obtain from app.config later
    cloudlaunch_url = os.environ.get('CLOUDLAUNCH_API_ENDPOINT',
                                     'http://localhost:8000/api/v1')
    cloudlaunch_token = os.environ.get('CLOUDLAUNCH_API_TOKEN')
    return APIClient(cloudlaunch_url, token=cloudlaunch_token)


@cachetools.cached(cachetools.TTLCache(maxsize=1, ttl=300))
def _get_pulsar_servers(app):
    """
    Returns an array of tuples, consisting of the pulsar url and auth token
    """
    client = _get_cloudlaunch_client(app)
    server_list = []
    # List servers sorted from oldest to newest, so that newly added servers
    # will be used before round-robin wrap around
    for deployment in client.deployments.list(
            application='pulsar-standalone', version='0.1',
            archived=False, status='SUCCESS', ordering='added'):
        launch_data = deployment.launch_task.result.get('pulsar', {})
        if launch_data and launch_data.get('api_url'):
            server_list.append(
                (launch_data.get('api_url'), launch_data.get('auth_token')))
    return server_list


def _get_next_pulsar_server(app):
    """
    Round-robin implementation for returning next available pulsar server
    """
    global current_server_index
    servers = _get_pulsar_servers(app)
    if current_server_index >= len(servers):
        current_server_index = 0
    if servers:
        next_server = servers[current_server_index]
        current_server_index += 1
        return next_server
    return None, None


def remote_pulsar_runner(app):
    url, token = _get_next_pulsar_server(app)
    return JobDestination(runner="pulsar",
                          params={"url": url, "private_token": token})
