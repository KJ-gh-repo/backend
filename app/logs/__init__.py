# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2022 Gemeente Amsterdam
import copy
import os
from typing import List, Union

from .config import BASE_LOGGING
from .filters import DebugQueryFilter
from .handlers import ColoredHandler

__all__ = ["ColoredHandler", "DebugQueryFilter", "get_configuration"]


def add_azure(_config):
    """
    Add the azure config if the variable ENABLE_AZURE is enabled.
    The reason it is not done with a filter is because of the registration of the
    connection_string that would cause issues and the connection to azure
    """
    connection_string = os.getenv('AZURE_APPLICATION_INSIGHTS_CONNECTION_STRING', None)
    if not connection_string:
        return

    _config['handlers']['azure'] = {
            'class': 'opencensus.ext.azure.log_exporter.AzureLogHandler',
            'connection_string': connection_string,
         }

    _config['loggers']['django']['handlers'] = ['azure', 'colorless']
    _config['loggers']['django.db.backends']['handlers'] = ['azure', 'colorless']


def get_configuration(local_apps: List[str], logging_level: Union[str, int]):
    """
    This function returns a dictionary config object that can be used as the
    LOGGING environment variable.

    It will construct a logger for every app passed via the local_apps
    list parameter with the given level in the logging_level.

    :param local_apps:
    :param logging_level:
    :return:
    """

    _config = copy.deepcopy(BASE_LOGGING)

    _handlers = ['colorize']
    if os.getenv('AZURE_APPLICATION_INSIGHTS_ENABLED') in [True, 'True', 'true', '1']:
        add_azure(_config)
        _handlers.append('azure')

    for app_name in local_apps:
        _config['loggers'].update(
            {app_name: {'level': logging_level, 'handlers': ['colorize']}}
        )

    return _config
