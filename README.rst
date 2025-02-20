========
pwclient
========

.. NOTE: If editing this, be sure to update the line numbers in 'doc/index'

.. image:: https://badge.fury.io/py/pwclient.svg
   :target: https://badge.fury.io/py/pwclient
   :alt: PyPi Status

.. image:: https://readthedocs.org/projects/pwclient/badge/?version=latest
   :target: https://pwclient.readthedocs.io/en/latest/?badge=latest
   :alt: Documentation Status

.. image:: https://github.com/getpatchwork/pwclient/actions/workflows/ci.yaml/badge.svg
   :target: https://github.com/getpatchwork/pwclient/actions/workflows/ci.yaml
   :alt: Build Status

*pwclient* is a VCS-agnostic tool for interacting with `Patchwork`__, the
web-based patch tracking system.

__ http://jk.ozlabs.org/projects/patchwork/


Installation
------------

The easiest way to install *pwclient* and its dependencies is using ``pip``. To
do so, run:

.. code-block:: bash

   $ pip install pwclient

You can also install *pwclient* manually. First, install the required
dependencies. On Fedora, run:

.. code-block:: bash

   $ sudo dnf install python-pbr

On Ubuntu, run:

.. code-block:: bash

   $ sudo apt-get install python-pbr

Once dependencies are installed, clone this repo and run ``setup.py``:
**(Preferred method for SIGNAL)**

.. code-block:: bash

   $ git clone https://github.com/getpatchwork/pwclient
   $ cd pwclient
   $ pip install --user .  # or 'sudo python setup.py install'

Getting Started
---------------

To use *pwclient*, you will need a ``.pwclientrc`` file, located in your home
directory (``$HOME`` or ``~``). Patchwork itself provides sample
``.pwclientrc`` files for projects at ``/project/{projectName}/pwclientrc/``.
For example, `here`__ is the ``.pwclientrc`` file for Patchwork itself.

__ https://patchwork.ozlabs.org/project/patchwork/pwclientrc/


```toml
# Sample .pwclientrc file for the patchwork project,
# running on patchwork.kernel.org. THIS IS USED in SIGNAL.
#
# Just append this file to your existing ~/.pwclientrc
# If you do not already have a ~/.pwclientrc, then copy this file to
# ~/.pwclientrc, and uncomment the following two lines:
[options]
default=linux-block

[linux-block]
url = https://patchwork.kernel.org/xmlrpc/

[linux-omap]
url = https://patchwork.kernel.org/xmlrpc/
```

Examples (that worked :-) )
-----------

In this example, I used one of the submitters fetched by the mailing-list-scrapper: Alex Shi.
The goal was to see if that user had any patches in patchwork.kernel.org.
If found, then it means we can use this tool to make the connection between mailing list's emails
and patches. This will be useful for SIGNAL.  

```shell
› pwclient list --submitter "Alex Shi" --in-depth --format csv > all_patches_by_alex.csv
› pwclient list --submitter "Alex Shi" --state Accepted --in-depth --format csv > all_accepted_patches_by_alex.csv
```


Development
-----------

If you're interested in contributing to *pwclient*, first clone the repo:

.. code-block:: bash

   $ git clone https://github.com/getpatchwork/pwclient
   $ cd pwclient

Create a *virtualenv*, then install the package in `editable`__ mode:

.. code-block:: bash

   $ virtualenv .venv
   $ source .venv/bin/activate
   $ pip install --editable .

__ https://pip.pypa.io/en/stable/reference/pip_install/#editable-installs


Documentation
-------------

Documentation is available on `Read the Docs`__

__ https://pwclient.readthedocs.io/
