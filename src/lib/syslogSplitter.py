

def split(bytes):
    """ Split an heroku syslog encoded payload using the octet counting method as described here
        https://tools.ietf.org/html/rfc6587#section-3.4.1
    """

    lines = []
    while len(bytes) > 0:
        # find first space character
        i = 0
        while bytes[i] != 32:  # 32 is white space in unicode
            i += 1
        msg_len = int(bytes[0:i].decode('utf-8'))
        msg = bytes[i + 1:i + msg_len + 1]

        # remove \n at the end of the line if found
        eol = msg[len(msg)-1]
        if eol == 10 or eol == 13:  # \n or \r in unicode
            msg = msg[:-1]

        lines.append(msg)

        bytes = bytes[i + 1 + msg_len:]
    return lines
