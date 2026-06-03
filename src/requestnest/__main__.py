"""Enable ``python -m requestnest`` as a PATH-independent entry point.

Mirrors the ``requestnest`` / ``rn`` console scripts so the CLI stays runnable
even when the install's scripts directory isn't on ``PATH`` — common on Windows
user-site (``pip install --user``) installs.
"""

from requestnest.cli import main

if __name__ == "__main__":
    main()
