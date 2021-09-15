# Patchwork command line client
# Copyright (C) 2018 Stephen Finucane <stephen@that.guru>
# Copyright (C) 2008 Nate Case <ncase@xes-inc.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later
from . import utils

_LIST_HEADERS = ('ID', 'Name', 'Email')


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

def list_people(people_dict_arr, format_str):
    if format_str in ['simple', 'table', 'csv']:
        output = []
        for each_person in people_dict_arr:
            item = [
                each_person['id'],
                each_person['name'],
                each_person['email'],
            ]
            
            output.append([])
            for idx, _ in enumerate(_LIST_HEADERS):
                output[-1].append(item[idx])
        utils.echo_via_pager(output, _LIST_HEADERS, format_str)
    else:
        for each_person in people_dict_arr:
            print(each_person)
