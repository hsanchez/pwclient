# Patchwork command line client
# Copyright (C) 2018 Stephen Finucane <stephen@that.guru>
# Copyright (C) 2008 Nate Case <ncase@xes-inc.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import collections
import io
import os
import re
import subprocess
import sys
import time
from typing import List

import tqdm
from dateutil import parser as dateparser

from . import people, projects, states, utils
from .xmlrpc import xmlrpclib

_LIST_HEADERS = (
    'ID', 'Date', 'Name', 'Submitter', 'State', 'Archived', 'Delegate', 'MessageId', 'CommitRef')


class Patch(object):
    """Nicer representation of a patch from the server."""

    def __init__(self, patch_dict):
        """Patch constructor.

        @patch_dict: The dictionary version of the patch.
        """
        # Make it easy to compare times of patches by getting an int.
        date_data_str = utils.ensure_str(patch_dict["date"])
        # self.time = time.mktime(time.strptime(str(patch_dict["date"].data, 'utf-8'),
        #                                       "%Y-%m-%d %H:%M:%S"))
        self.time = time.mktime(time.strptime(date_data_str, "%Y-%m-%d %H:%M:%S"))

        self.version, self.part_num, self.num_parts = \
            self._parse_patch_name(patch_dict["name"])

        # Add a few things to make it easier...
        self.id = patch_dict["id"]
        self.project = utils.ensure_str(patch_dict["project"])
        self.project_id = patch_dict["project_id"]
        self.name = patch_dict["name"]
        self.submitter_id = patch_dict["submitter_id"]

        # Keep the dict in case we need anything else...
        self.dict = patch_dict

    def csvdict(self) -> dict:
        return {
            'id': self.id,
            'project': self.project,
            'date': self.time,
            'filename': self.dict['filename'],
            'msgid': self.dict['msgid'],
            'name': self.dict['name'],
            'state': utils.ensure_str(self.dict['state']),
            'submitter': utils.ensure_str(self.dict['submitter']),
            'commit': self.dict["commit_ref"],
            'hash': self.dict['hash']
        }

    def csv_headers(self) -> List[str]:
        return list(self.csvdict().keys())

    @staticmethod
    def _parse_patch_name(name):
        """Parse a patch name into version, part_num, num_parts.

        @name: The patch name.
        @return: (version, part_num, num_parts)
        """
        mo = re.match(r"\[v(\d*),(\d*)/(\d*)\]", name)
        if mo:
            return mo.groups()

        mo = re.match(r"\[(\d*)/(\d*)\]", name)
        if mo:
            return (1, mo.groups()[0], mo.groups()[1])

        mo = re.match(r"\[v(\d*)]", name)
        if mo:
            return (mo.groups()[0], 1, 1)

        return (1, 1, 1)

    def __str__(self):
        return str(self.dict)

    def __repr__(self):
        return repr(self.dict)


class Filter(object):

    """Filter for selecting patches."""

    def __init__(self):
        # These fields refer to specific objects, so they are special
        # because we have to resolve them to IDs before passing the
        # filter to the server
        self.state = ""
        self.project = ""

        # The dictionary that gets passed to via XML-RPC
        self.d = {}

    def add(self, field, value):
        if field == 'state':
            self.state = value
        elif field == 'project':
            self.project = value
        else:
            # OK to add directly
            self.d[field] = value

    def resolve_ids(self, rpc):
        """Resolve State, Project, and Person IDs based on filter strings."""
        if self.state != "":
            id = states.state_id_by_name(rpc, self.state)
            if id == 0:
                sys.stderr.write("Note: No State found matching %s*, "
                                 "ignoring filter\n" % self.state)
            else:
                self.d['state_id'] = id

        if self.project is not None:
            id = projects.project_id_by_name(rpc, self.project)
            if id == 0:
                sys.stderr.write("Note: No Project found matching %s, "
                                 "ignoring filter\n" % self.project)
            else:
                self.d['project_id'] = id

    def __str__(self):
        """Return human-readable description of the filter."""
        return str(self.d)


def patch_id_from_hash(rpc, project, hash):
    try:
        patch = rpc.patch_get_by_project_hash(project, hash)
    except xmlrpclib.Fault:
        # the server may not have the newer patch_get_by_project_hash function,
        # so fall back to hash-only.
        patch = rpc.patch_get_by_hash(hash)

    if patch == {}:
        sys.stderr.write("No patch has the hash provided\n")
        sys.exit(1)

    patch_id = patch['id']
    # be super paranoid
    try:
        patch_id = int(patch_id)
    except ValueError:
        sys.stderr.write("Invalid patch ID obtained from server\n")
        sys.exit(1)
    return patch_id


def _list_patches(patches, rpc=None, format_str=None, get_recs_only=False, echo_via_pager=False):
    """Dump a list of patches to stdout."""
    if get_recs_only and not echo_via_pager:
        return [patch for patch in patches]
    elif echo_via_pager:
        assert rpc is not None
        def person_info_str(person_dic):
            return utils.trim('%s (%s)' % (person_dic.get('name', ''),
                                           person_dic.get('email', '')))
        
        # New formatting functionality and will
        # replace the old formatting api next.
        output = []
        for patch in patches:
            submitter_str = person_info_str(people.person_get(rpc, patch['submitter_id']))
            delegate_str = person_info_str(people.person_get(rpc, patch['delegate_id']))
            commit_ref_str = utils.ensure_str(patch['commit_ref']) 
            item = [
                patch['id'],
                utils.ensure_str(patch['date']),
                utils.trim(patch['name']),
                submitter_str if '()' not in submitter_str else 'NA',
                patch['state'],
                'yes' if patch['archived'] else 'no',
                delegate_str if '()' not in delegate_str else 'NA',
                utils.ensure_str(patch['msgid']).strip("<>"),
                commit_ref_str if commit_ref_str != '' else 'NA',
            ]
            
            output.append([])
            for idx, _ in enumerate(_LIST_HEADERS):
                output[-1].append(item[idx])
            
        utils.echo_via_pager(output, _LIST_HEADERS, format_str)
        return []
    # old formatting api
    if format_str:
        format_field_re = re.compile("%{([a-z0-9_]+)}")

        def patch_field(matchobj):
            fieldname = matchobj.group(1)

            if fieldname == "_msgid_":
                # naive way to strip < and > from message-id
                val = str(patch["msgid"]).strip("<>")
            else:
                val = str(patch[fieldname])

            return val

        for patch in patches:
            print(format_field_re.sub(patch_field, format_str))
    else:
        print("%-7s %-12s %-15s %-15s %s" % ("ID", "State", "MessageId", "Date", "Name"))
        print("%-7s %-12s %-15s %-15s %s"  % ("--", "-----", "----", "----","----"))
        for patch in patches:
            date_value = utils.ensure_str(patch['date'])
            date_str = dateparser.parse(date_value).strftime('%Y-%m-%dT%H:%M:%S')
            print("%-7d %-12s %-15s %-15s %s" %
                  (patch['id'], patch['state'], patch['msgid'], date_str, patch['name']))

    return []

def action_list(rpc, filters, submitter_str, delegate_str, series_str, format_str=None, get_recs_only=False):
    filters.resolve_ids(rpc)
    
    if series_str and series_str != "":
        try:
            patch_id = int(series_str)
        except:
            sys.stderr.write("Invalid patch ID given\n")
            sys.exit(1)

        patches = patch_id_to_series(rpc, patch_id)
        return _list_patches([patch.dict for patch in patches], format_str=format_str, get_recs_only=get_recs_only)

    if submitter_str is not None:
        submitter_patches = []
        ids = people.person_ids_by_name(rpc, submitter_str)
        if not get_recs_only:
            print(f"people found: {len(ids)}")
        if len(ids) == 0:
            sys.stderr.write("Note: Nobody found matching *%s*\n" %
                             submitter_str)
        else:
            for id in ids:
                person = rpc.person_get(id)
                if not get_recs_only:
                    print('Patches submitted by %s <%s>:' %
                        (person['name'], person['email']))
                f = filters
                f.add("submitter_id", id)
                patches = rpc.patch_list(f.d)
                submitter_patches += _list_patches(patches, format_str, get_recs_only=get_recs_only)
        return submitter_patches

    if delegate_str is not None:
        delegate_patches = []
        ids = people.person_ids_by_name(rpc, delegate_str)
        if len(ids) == 0:
            sys.stderr.write("Note: Nobody found matching *%s*\n" %
                             delegate_str)
        else:
            for id in ids:
                person = rpc.person_get(id)
                if not get_recs_only:
                    print('Patches delegated to %s <%s>:' %
                        (person['name'], person['email']))
                f = filters
                f.add("delegate_id", id)
                patches = rpc.patch_list(f.d)
                delegate_patches += _list_patches(patches, format_str, get_recs_only=get_recs_only)
        return delegate_patches

    patches = rpc.patch_list(filters.d)
    return _list_patches(patches, format_str, get_recs_only=get_recs_only)


def get_patch_objects(rpc, filters, submitter_str, delegate_str, series_str, format_str=None):
    return action_list(rpc, filters, submitter_str, delegate_str, series_str, format_str, get_recs_only=True)


def action_list_all_patchwork(rpc, filters, submitter_str, delegate_str, series_str, format_str=None, get_recs_only=False,
                              proj_scope = None):
    if proj_scope:
        proj_recs = [(-1, proj) for proj in proj_scope]
    else:
        proj_recs = projects.action_list(rpc, get_recs_only=True)
    all_patches = []
    for (_, linkname_) in tqdm.tqdm(proj_recs, disable=get_recs_only):
        # print(f"Exploring project: {linkname_}")
        # override project's link name 
        filters.add('project', linkname_)
        try:
            matched = get_patch_objects(rpc, filters, submitter_str, delegate_str, series_str, format_str)
            if matched and len(matched) > 0:
                all_patches += matched
                # print(f"Matched found. Found {len(matched)} patches for {linkname_}")

            # break if msg id has been found
            if matched and 'msgid' in filters.d:
                break
            # break if series given series_str (or patch_id) has been fetched
            elif matched and series_str:
                break
        except Exception as e:
            # print(f"Unable to explore project {linkname_}. Error: {e}", file=sys.stderr)
            raise e

    if get_recs_only:
        return all_patches

    return _list_patches(all_patches, rpc=rpc, format_str=format_str, echo_via_pager=True)


def patch_id_to_series(rpc, patch_id):
    """Take a patch ID and return a list of patches in the same series.

    This function uses the following heuristics to find patches in a series:
    - It searches for all patches with the same submitter that the same version
      number and same number of parts.
    - It allows patches to span multiple projects (though they must all be on
      the same patchwork server), though it prefers patches that are part of
      the same project.  This handles cases where some parts in a series might
      have only been sent to a topic project (like "linux-mmc").
    - For each part number it finds the matching patch that has a date value
      closest to the original patch.

    It would be nice to use "Message-ID" and "In-Reply-To", but that's not
    exported to the xmlrpc interface as far as I can tell.  :(

    @patch_id: The patch ID that's part of the series.
    @return: A list of patches in the series.
    """
    # Find this patch
    patch = Patch(rpc.patch_get(patch_id))

    # Get the all patches by the submitter, ignoring project.
    filter = Filter()
    filter.add("submitter_id", patch.submitter_id)
    all_patches = [Patch(p) for p in rpc.patch_list(filter.d)]

    # Whittle down--only those with matching version / num_parts.
    key = (patch.version, patch.num_parts)
    all_patches = [p for p in all_patches if (p.version, p.num_parts) == key]

    # Organize by part_num.
    by_part_num = collections.defaultdict(list)
    for p in all_patches:
        by_part_num[p.part_num].append(p)

    # Find the part that's closest in time to ours for each part num.
    final_list = []
    for part_num, patch_list in sorted(iter(by_part_num.items())):
        # Create a list of tuples to make sorting easier.  We want to find
        # the patch that has the closet time.  If there's a tie then we want
        # the patch that has the same project ID...
        patch_list = [(abs(p.time - patch.time),
                       abs(p.project_id - patch.project_id),
                       p) for p in patch_list]

        best = sorted(patch_list)[0][-1]
        final_list.append(best)

    return final_list


def action_info(rpc, patch_id):
    patch = rpc.patch_get(patch_id)

    if patch == {}:
        sys.stderr.write("Error getting information on patch ID %d\n" %
                         patch_id)
        sys.exit(1)

    s = "Information for patch id %d" % (patch_id)
    print(s)
    print('-' * len(s))
    for key, value in sorted(patch.items()):
        # Some values are transferred as Binary data, these are encoded in
        # utf-8. As of Python 3.9 xmlrpclib.Binary.__str__ however assumes
        # latin1, so decode explicitly
        value = utils.ensure_str(value)
        # if type(value) == xmlrpclib.Binary:
        #     value = str(value.data, 'utf-8')
        print("- %- 14s: %s" % (key, value))


def action_get(rpc, patch_id):
    patch = rpc.patch_get(patch_id)
    mbox = rpc.patch_get_mbox(patch_id)

    if patch == {} or len(mbox) == 0:
        sys.stderr.write("Unable to get patch %d\n" % patch_id)
        sys.exit(1)

    base_fname = fname = os.path.basename(patch['filename'])
    fname += '.patch'
    i = 0
    while os.path.exists(fname):
        fname = "%s.%d.patch" % (base_fname, i)
        i += 1

    with io.open(fname, 'x', encoding='utf-8') as f:
        f.write(mbox)
        print('Saved patch to %s' % fname)


def action_view(rpc, patch_ids):
    mboxes = []

    for patch_id in patch_ids:
        mbox = rpc.patch_get_mbox(patch_id)
        if mbox:
            mboxes.append(mbox)

    if not mboxes:
        return

    pager = os.environ.get('PAGER')
    if pager:
        # TODO(stephenfin): Use as a context manager when we drop support for
        # Python 2.7
        pager = subprocess.Popen(pager.split(), stdin=subprocess.PIPE)
        try:
            pager.communicate(input='\n'.join(mboxes).encode('utf-8'))
        finally:
            if pager.stdout:
                pager.stdout.close()
            if pager.stderr:
                pager.stderr.close()
            if pager.stdin:
                pager.stdin.close()
            pager.wait()
    else:
        for mbox in mboxes:
            if sys.version_info < (3, 0):
                mbox = mbox.encode('utf-8')
            print(mbox)


def action_apply(rpc, patch_id, apply_cmd=None):
    patch = rpc.patch_get(patch_id)
    if patch == {}:
        sys.stderr.write("Error getting information on patch ID %d\n" %
                         patch_id)
        sys.exit(1)

    if apply_cmd is None:
        print('Applying patch #%d to current directory' % patch_id)
        apply_cmd = ['patch', '-p1']
    else:
        print('Applying patch #%d using "%s"' %
              (patch_id, ' '.join(apply_cmd)))

    print('Description: %s' % patch['name'])
    mbox = rpc.patch_get_mbox(patch_id)
    if len(mbox) > 0:
        proc = subprocess.Popen(apply_cmd, stdin=subprocess.PIPE)
        proc.communicate(mbox.encode('utf-8'))
        return proc.returncode
    else:
        sys.stderr.write("Error: No patch content found\n")
        sys.exit(1)


def action_update(rpc, patch_id, state=None, archived=None, commit=None):
    patch = rpc.patch_get(patch_id)
    if patch == {}:
        sys.stderr.write("Error getting information on patch ID %d\n" %
                         patch_id)
        sys.exit(1)

    params = {}

    if state:
        state_id = states.state_id_by_name(rpc, state)
        if state_id == 0:
            sys.stderr.write("Error: No State found matching %s*\n" % state)
            sys.exit(1)
        params['state'] = state_id

    if commit:
        params['commit_ref'] = commit

    if archived:
        params['archived'] = archived == 'yes'

    success = False
    try:
        success = rpc.patch_set(patch_id, params)
    except xmlrpclib.Fault as f:
        sys.stderr.write("Error updating patch: %s\n" % f.faultString)

    if not success:
        sys.stderr.write("Patch not updated\n")
