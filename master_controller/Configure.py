""" Functions executed when the master controller is configured
"""
__author__ = 'David Terrett'

from docker import Client
import threading 

import logger
import os

from .HeartbeatListener import heartbeat_listener
from .slave_map import slave_map

class Configure(threading.Thread):
    """ Does the actual work of configuring the system
    """
    def __init__(self, mc):
        """ Stores the state machine

        The state machine is needed so that we can post a "configure done"
        event when the system is configured.
        """
        self._mc = mc
        super(Configure, self).__init__()

    def run(self):
        """ Thread run routine
        """
        logger.trace('starting configuration')
        
        # Start the local telescope state application
        _start_slave('lts', slave_map['lts'])
        logger.trace('configure done')
        self._mc.post_event(['configure done'])

def _start_slave(name, properties):
    """ Start a slave controller
    """
    if properties['type'] == 'docker':
        _start_docker_slave(name, properties)
    else:
       logger.error('failed to start "' + name + '": "' + properties['type'] +
                    '" is not a known slave type')

def _start_docker_slave(name, properties):
    """ Start a slave controller that is a Docker container
    """

    # Create a Docker client
    client = Client(version='1.21', base_url=properties['engine_url'])

    # Create a container and store its id in the properties array
    image = properties['image']
    heartbeat_port = properties['heartbeat_port']
    rpc_port = properties['rpc_port']
    container_id = client.create_container(image=image,
                   command=['/home/sdp/docker_slave.py', 
                            name, 
                            heartbeat_port,
                            rpc_port
                           ],
		   volumes=['/home/sdp/components/'],
		   host_config=client.create_host_config(binds={
        		os.getcwd()+'/components': {
            		'bind': '/home/sdp/components/',
            		'mode': 'rw',
        		}
                   }))['Id']

    # Start it
    client.start(container_id)
    info = client.inspect_container(container_id)
    ip_address = info['NetworkSettings']['IPAddress']
    properties['address'] = ip_address
    properties['state'] = 'running'
    properties['container_id'] = container_id
    properties['timeout counter'] = properties['timeout']
    logger.info(name + ' started in container ' + container_id + ' at ' +
                ip_address)

    # Connect the heartbeat listener to the address it is sending heartbeats
    # to.
    heartbeat_listener.connect(ip_address, heartbeat_port)
