# Patchwork command line client
# Copyright (C) 2018 Stephen Finucane <stephen@that.guru>
# Copyright (C) 2008 Nate Case <ncase@xes-inc.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later


def person_ids_by_name(rpc, name, exact_match=False):
    """Given a partial name or email address, return a list of the
    person IDs that match."""
    if len(name) == 0:
        return []
    people = rpc.person_list(name, 0)
    if not exact_match:
        return [x['id'] for x in people]
    else:
        return [x['id'] for x in people if x['name'] == name]


def person_get(rpc, person_id):
    if not person_id:
        return {}
    person_id = int(person_id)
    person = rpc.person_get(person_id)
    if not person:
        return {}
    return {'name': person['name'], 'email': person['email']}