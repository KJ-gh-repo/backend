# SPDX-License-Identifier: MPL-2.0
# Copyright (C) 2023 Gemeente Amsterdam
from elasticsearch_dsl import Boolean, Document, Integer, Text


class StatusMessage(Document):
    id = Integer()
    title = Text(analyzer='dutch')
    text = Text(analyzer='dutch')
    state = Text()
    active = Boolean()

    class Index:
        name = 'status_messages'
