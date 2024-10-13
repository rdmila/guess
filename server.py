import selectors
import socket
import sqlite3
from random import randrange

sel = selectors.DefaultSelector()

user_cnt = 0
user_to_guess_cnt = dict()

con = sqlite3.connect("experiment.db")
cur = con.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS guesses(exp_no, guess_no, user_id, number)")
cur.execute("CREATE TABLE IF NOT EXISTS experiments(exp_no, answer)")
exp_no = cur.execute("SELECT MAX(exp_no) FROM experiments").fetchone()
if exp_no == None:
    exp_no = 1

answer = None

admin_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
user_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

def accept(sock, mask, is_admin):
    conn, addr = sock.accept()
    print('accepted', conn, 'from', addr)
    conn.setblocking(False)
    id = 0
    if not is_admin:
        global user_cnt
        user_cnt += 1
        id = user_cnt
    sel.register(conn, selectors.EVENT_READ, (read, (is_admin, id)))


def read(conn, mask, opts):
    global answer
    is_admin, user_id = opts
    req = conn.recv(500).decode()
    if is_admin:
        command, param = req.split()
        if command == 'start':
            answer = int(param)
            for sel_key in sel.get_map().values():
                if (sel_key.fileobj in (admin_sock, user_sock)):
                    continue
                print(f"sending to fd {sel_key.fd}")
                sel_key.fileobj.send(b'start')

    else:
        if req == 'history':
            h = cur.execute("""SELECT exp_no, guess_no, number FROM guesses
                WHERE user_id=? SORT BY exp_no DESC, guess_no ASC""", (user_id, )).fetchall()
            print(h) # TODO
        else:
            if answer == None:
                conn.send(b'not started')
            x = int(req)
            if x > answer:
                conn.send(b'x>a')
            elif x < answer:
                conn.send(b'x<a')
            else:
                conn.send(b'x=a')
            if user_id not in user_to_guess_cnt:
                user_to_guess_cnt[user_id] = 0
            user_to_guess_cnt[user_id] += 1
            cur.execute("INSERT INTO guesses VALUES (?, ?, ?, ?)", 
                        (exp_no, user_to_guess_cnt[user_id], user_id, x))
            


admin_sock.bind(('localhost', 1234))
admin_sock.listen(5)
admin_sock.setblocking(False)
sel.register(admin_sock, selectors.EVENT_READ, (accept, True))

user_sock.bind(('localhost', 1235))
user_sock.listen(5)
user_sock.setblocking(False)
sel.register(user_sock, selectors.EVENT_READ, (accept, False))

while True:
    events = sel.select()
    for key, mask in events:
        callback, opts = key.data
        callback(key.fileobj, mask, opts)

