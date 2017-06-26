
# def split(input_string):
#     lines = []
#     while len(input_string) > 0:
#         print("l", input_string)
#         length, rest = input_string.split(' ', 1)
#         length = int(length)
#         lines.append(rest[0:length].replace('\n', ''))
#         input_string = rest[length:]
#     return lines

# heroku is octet counting https://tools.ietf.org/html/rfc6587#section-3.4.1
def split(bytes):
    lines = []
    while len(bytes) > 0:
        # find first space character
        i = 0
        while (bytes[i] != 32):
            i+=1
        msgLen = int(bytes[0:i].decode('utf-8'))

        msg = bytes[i + 1:i + msgLen + 1]

        # remove \n at the end of the line if found
        eol = msg[len(msg)-1]
        if eol == 10 or eol == 13:
            msg = msg[:-1]

        lines.append(msg)

        bytes = bytes[i + 1 + msgLen:]
    return lines
