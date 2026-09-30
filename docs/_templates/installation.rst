Activate the `virtual environment <https://docs.python.org/3/tutorial/venv.html>`_ in which you want to install Scenic.
To create and activate a new virtual environment called :file:`venv`, you can run the following commands:

.. venv-setup-start
.. code-block:: text

    python3 -m venv venv
    source venv/bin/activate
.. venv-setup-end

Once your virtual environment is activated, you no longer need to use a name like ``python3`` or ``python3.11``; use just :command:`python` to ensure you're running the copy of Python in your virtual environment.

Next, make sure your :command:`pip` tool is up-to-date:

.. code-block:: text

    python -m pip install --upgrade pip

Now you can install Scenic either from the repository or from PyPI:

.. tabs::

    .. tab:: Repository

        The following commands will clone the `Scenic repository <https://github.com/Scenic-Foundation/Scenic>`_ into a folder called :file:`Scenic` and install Scenic from there.
        It is an "editable install", so if you later update the repository with :command:`git pull` or make changes to the code yourself, you won't need to reinstall Scenic.

        .. code-block:: text

            git clone https://github.com/Scenic-Foundation/Scenic
            cd Scenic
            python -m pip install -e .

        If you will be developing Scenic, you will want to use a variant of the last command to install additional development dependencies: see :doc:`developing`.

    .. tab:: PyPI

        The following command will install the latest full release of Scenic from `PyPI <https://pypi.org/project/scenic/>`_:

        .. code-block:: text

            python -m pip install scenic

        Note that this command skips experimental alpha and beta releases, preferring stable versions.
        If you want to get the very latest version available on PyPI (which may still be behind the repository), run:

        .. code-block:: text

            python -m pip install --pre scenic

        You can also install specific versions with a command like:

        .. code-block:: text

            python -m pip install scenic==2.0.0
