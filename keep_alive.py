from threading import Thread

from flask import Flask

from constants import PORT_NUMBER

app = Flask("")


@app.route("/")
def home():
    return "Hello. I am alive!"


def run():
    app.run(host="0.0.0.0", port=PORT_NUMBER)


def keep_alive():
    t = Thread(target=run)
    t.start()
