# Patchwork command line client
# Copyright (C) 2018 Stephen Finucane <stephen@that.guru>
# Copyright (C) 2008 Nate Case <ncase@xes-inc.com>
#
# SPDX-License-Identifier: GPL-2.0-or-later

import configparser
import csv
import io
import os
import re
import shutil
import subprocess
import sys
import typing as ty

from tabulate import tabulate

from .xmlrpc import xmlrpclib


def ensure_str(s: ty.Any) -> str:
    if s is None:
        s = ''
    elif isinstance(s, bytes):
        s = s.decode('utf-8', 'strict')
    elif not isinstance(s, str):
        s = str(s)
    elif type(s) == xmlrpclib.Binary:
        s = str(s.data, 'utf-8')
    return s

def trim(string: str, length: int = 70) -> str:
    """Trim a string to the given length."""
    return (string[:length - 1] + '...') if len(string) > length else string


def strip_trim(string: str, length: int = 70) -> str:
    # thx to https://stackoverflow.com/questions/14596884/
    return trim(re.sub("[\(\[].*?[\)\]]", "", string))


def git_config(value: str) -> str:
    """Parse config from ``git-config`` cache.

    Returns:
        Matching setting for ``key`` if available, else None.
    """
    cmd = ['git', 'config', value]

    try:
        output = subprocess.check_output(cmd)
    except subprocess.CalledProcessError:
        output = b''

    return output.decode('utf-8').strip()


def _tabulate(
    output: ty.List[ty.Tuple[str, ty.Any]],
    headers: ty.List[str],
    fmt: str,
) -> str:
    fmt = fmt or 'table'

    if fmt == 'table':
        return tabulate(output, headers, tablefmt='psql')
    elif fmt == 'simple':
        return tabulate(output, headers, tablefmt='simple')
    elif fmt == 'csv':
        result = io.StringIO()
        writer = csv.writer(
            result, quoting=csv.QUOTE_ALL, lineterminator=os.linesep)
        writer.writerow([ensure_str(h) for h in headers])
        for item in output:
            writer.writerow([ensure_str(i) for i in item])
        return result.getvalue()

    sys.exit(1)


def _echo_via_pager(pager: str, output: str) -> None:
    env = dict(os.environ)
    # When the LESS environment variable is unset, Git sets it to FRX (if
    # LESS environment variable is set, Git does not change it at all).
    if 'LESS' not in env:
        env['LESS'] = 'FRX'

    proc = subprocess.Popen(pager.split(), stdin=subprocess.PIPE, env=env)

    try:
        proc.communicate(input=output.encode('utf-8', 'strict'))
    except (IOError, KeyboardInterrupt):
        pass
    else:
        if proc.stdin:
            proc.stdin.close()

    while True:
        try:
            proc.wait()
        except KeyboardInterrupt:
            pass
        else:
            break


def echo_via_pager(
    output: ty.List[ty.Tuple[str, ty.Any]],
    headers: ty.List[str],
    fmt: str,
) -> None:
    """Echo using git's default pager.

    Wrap ``click.echo_via_pager``, setting some environment variables in the
    process to mimic the pager settings used by Git:

        The order of preference is the ``$GIT_PAGER`` environment variable,
        then ``core.pager`` configuration, then ``$PAGER``, and then the
        default chosen at compile time (usually ``less``).
    """
    out = _tabulate(output, headers, fmt)

    pager = os.environ.get('GIT_PAGER', None)
    if pager:
        _echo_via_pager(pager, out)
        return

    pager = git_config('core.parser')
    if pager:
        _echo_via_pager(pager, out)
        return

    pager = os.environ.get('PAGER', None)
    if pager:
        _echo_via_pager(pager, out)
        return

    _echo_via_pager('less', out)


def migrate_old_config_file(config_file, config):
    """Convert a config file to the Patchwork 1.0 format."""
    sys.stderr.write('%s is in the old format. Migrating it...' %
                     config_file)

    old_project = config.get('base', 'project')

    new_config = configparser.ConfigParser()
    new_config.add_section('options')

    new_config.set('options', 'default', old_project)
    new_config.add_section(old_project)

    new_config.set(old_project, 'url', config.get('base', 'url'))
    if config.has_option('auth', 'username'):
        new_config.set(
            old_project, 'username', config.get('auth', 'username'))
    if config.has_option('auth', 'password'):
        new_config.set(
            old_project, 'password', config.get('auth', 'password'))

    old_config_file = config_file + '.orig'
    shutil.copy2(config_file, old_config_file)

    with open(config_file, 'w') as fd:
        new_config.write(fd)

    sys.stderr.write(' Done.\n')
    sys.stderr.write(
        'Your old %s was saved to %s\n' % (config_file, old_config_file))
    sys.stderr.write(
        'and was converted to the new format. You may want to\n')
    sys.stderr.write('inspect it before continuing.\n')


if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read(sys.argv[1])

    migrate_old_config_file(sys.argv[1], config)
