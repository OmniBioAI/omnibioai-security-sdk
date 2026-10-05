"""
OmniBioAI exceptions.

Purpose:
    Defines SecurityException, Unauthorized and Forbidden for exceptions.

Author:
    Manish Kumar <manish@omnibioai.org>
"""

class SecurityException(Exception):
    pass


class Unauthorized(SecurityException):
    pass


class Forbidden(SecurityException):
    pass