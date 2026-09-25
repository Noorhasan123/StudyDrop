from flask import Flask, render_template, request, redirect, url_for, send_from_directory
from datetime import datetime, timedelta
import sqlite3
import random
import string
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    static_folder=os.path.join(BASE_DIR, "static"),
    static_url_path="/static"
)



@app.before_request
def automatic_cleanup():
    if request.endpoint != "static":
        cleanup_expired_rooms()

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DATABASE = "database.db"


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
    CREATE TABLE IF NOT EXISTS rooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        room_code TEXT UNIQUE NOT NULL,
        room_name TEXT NOT NULL,
        expires_at TEXT
    )
""")

    try:
        conn.execute("ALTER TABLE rooms ADD COLUMN expires_at TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    conn.execute("""
        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_code TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_code TEXT NOT NULL,
            content TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_code TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def generate_room_code():
    while True:
        code = ''.join(
            random.choices(
                string.ascii_uppercase + string.digits,
                k=6
            )
        )

        conn = get_db()

        room = conn.execute(
            "SELECT * FROM rooms WHERE room_code = ?",
            (code,)
        ).fetchone()

        conn.close()

        if room is None:
            return code

def is_room_expired(room_code):

    conn = get_db()

    room = conn.execute(
        "SELECT expires_at FROM rooms WHERE room_code = ?",
        (room_code,)
    ).fetchone()

    conn.close()

    if room is None:
        return True

    if room["expires_at"] is None:
        return False

    expiry_time = datetime.fromisoformat(room["expires_at"])

    return datetime.now() >= expiry_time


def delete_expired_room(room_code):

    conn = get_db()

    # Get uploaded files of the room
    resources = conn.execute(
        "SELECT file_path FROM resources WHERE room_code = ?",
        (room_code,)
    ).fetchall()

    # Delete physical files
    for resource in resources:

        file_path = resource["file_path"]

        if os.path.exists(file_path):
            os.remove(file_path)

    # Delete database records
    conn.execute(
        "DELETE FROM resources WHERE room_code = ?",
        (room_code,)
    )

    conn.execute(
        "DELETE FROM notes WHERE room_code = ?",
        (room_code,)
    )

    conn.execute(
        "DELETE FROM links WHERE room_code = ?",
        (room_code,)
    )

    conn.execute(
        "DELETE FROM rooms WHERE room_code = ?",
        (room_code,)
    )

    conn.commit()
    conn.close()


def cleanup_expired_rooms():
    conn = get_db()

    rooms = conn.execute(
        "SELECT room_code, expires_at FROM rooms WHERE expires_at IS NOT NULL"
    ).fetchall()

    conn.close()

    for room in rooms:
        if datetime.now() >= datetime.fromisoformat(room["expires_at"]):
            delete_expired_room(room["room_code"])


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/create-room", methods=["GET", "POST"])
def create_room():

    if request.method == "POST":

        room_name = request.form["room_name"].strip()
        expiry = request.form.get("expiry", "0")

        if not room_name:
            return "Room name cannot be empty."

        room_code = generate_room_code()

        # Calculate expiry time
        if expiry == "0":
            expires_at = None
        else:
            hours = int(expiry)
            expires_at = (
                datetime.now() + timedelta(hours=hours)
            ).isoformat()

        conn = get_db()

        conn.execute(
            """
            INSERT INTO rooms
            (room_code, room_name, expires_at)
            VALUES (?, ?, ?)
            """,
            (room_code, room_name, expires_at)
        )

        conn.commit()
        conn.close()

        return redirect(url_for("room", room_code=room_code))

    return render_template("create_room.html")


@app.route("/room/<room_code>")
def room(room_code):

    conn = get_db()

    room_data = conn.execute(
        "SELECT * FROM rooms WHERE room_code = ?",
        (room_code,)
    ).fetchone()

    if room_data is None:
        conn.close()
        return "Room not found."

    # Check room expiry
    if room_data["expires_at"] is not None:

        expiry_time = datetime.fromisoformat(
            room_data["expires_at"]
        )

        if datetime.now() >= expiry_time:

            conn.close()

            delete_expired_room(room_code)

            return "This study room has expired and has been deleted."

    resources = conn.execute(
        "SELECT * FROM resources WHERE room_code = ?",
        (room_code,)
    ).fetchall()

    notes = conn.execute(
        "SELECT * FROM notes WHERE room_code = ? ORDER BY id DESC",
        (room_code,)
    ).fetchall()

    links = conn.execute(
        "SELECT * FROM links WHERE room_code = ? ORDER BY id DESC",
        (room_code,)
    ).fetchall()

    conn.close()

    return render_template(
        "room.html",
        room=room_data,
        resources=resources,
        notes=notes,
        links=links
    )


@app.route("/upload/<room_code>", methods=["POST"])
def upload_file(room_code):

    if is_room_expired(room_code):
        return "This study room has expired."

    file = request.files.get("file")

    if file is None or file.filename == "":
        return "No file selected."

    filename = file.filename

    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )

    file.save(file_path)

    conn = get_db()

    conn.execute(
        """
        INSERT INTO resources
        (room_code, file_name, file_path)
        VALUES (?, ?, ?)
        """,
        (room_code, filename, file_path)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("room", room_code=room_code))


@app.route("/download/<room_code>/<filename>")
def download_file(room_code, filename):

    if is_room_expired(room_code):
        return "This study room has expired."

    conn = get_db()

    resource = conn.execute(
        """
        SELECT * FROM resources
        WHERE room_code = ? AND file_name = ?
        """,
        (room_code, filename)
    ).fetchone()

    conn.close()

    if resource is None:
        return "File not found."

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename,
        as_attachment=True
    )

@app.route("/preview/<room_code>/<filename>")
def preview_file(room_code, filename):

    if is_room_expired(room_code):
        return "This study room has expired."

    conn = get_db()

    resource = conn.execute(
        """
        SELECT * FROM resources
        WHERE room_code = ? AND file_name = ?
        """,
        (room_code, filename)
    ).fetchone()

    conn.close()

    if resource is None:
        return "File not found."

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename,
        as_attachment=False
    )


@app.route("/add-note/<room_code>", methods=["POST"])
def add_note(room_code):

    if is_room_expired(room_code):
        return "This study room has expired."

    content = request.form.get("content", "").strip()

    if not content:
        return "Note cannot be empty."

    conn = get_db()

    conn.execute(
        """
        INSERT INTO notes (room_code, content)
        VALUES (?, ?)
        """,
        (room_code, content)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("room", room_code=room_code))


@app.route("/add-link/<room_code>", methods=["POST"])
def add_link(room_code):

    if is_room_expired(room_code):
        return "This study room has expired."

    title = request.form.get("title", "").strip()
    url = request.form.get("url", "").strip()

    if not title or not url:
        return "Title and URL are required."

    conn = get_db()

    conn.execute(
        """
        INSERT INTO links (room_code, title, url)
        VALUES (?, ?, ?)
        """,
        (room_code, title, url)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("room", room_code=room_code))

@app.route("/delete-file/<int:file_id>/<room_code>", methods=["POST"])
def delete_file(file_id, room_code):

    if is_room_expired(room_code):
        return "This study room has expired."

    conn = get_db()

    file = conn.execute(
        "SELECT * FROM resources WHERE id = ? AND room_code = ?",
        (file_id, room_code)
    ).fetchone()

    if file is None:
        conn.close()
        return "File not found."

    # Delete physical file
    if os.path.exists(file["file_path"]):
        os.remove(file["file_path"])

    # Delete database record
    conn.execute(
        "DELETE FROM resources WHERE id = ? AND room_code = ?",
        (file_id, room_code)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("room", room_code=room_code))


@app.route("/delete-note/<int:note_id>/<room_code>", methods=["POST"])
def delete_note(note_id, room_code):

    if is_room_expired(room_code):
        return "This study room has expired."

    conn = get_db()

    conn.execute(
        "DELETE FROM notes WHERE id = ? AND room_code = ?",
        (note_id, room_code)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("room", room_code=room_code))


@app.route("/delete-link/<int:link_id>/<room_code>", methods=["POST"])
def delete_link(link_id, room_code):

    if is_room_expired(room_code):
        return "This study room has expired."

    conn = get_db()

    conn.execute(
        "DELETE FROM links WHERE id = ? AND room_code = ?",
        (link_id, room_code)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("room", room_code=room_code))


@app.route("/join-room", methods=["GET", "POST"])
def join_room():

    if request.method == "POST":

        room_code = request.form["room_code"].upper().strip()

        conn = get_db()

        room = conn.execute(
            "SELECT * FROM rooms WHERE room_code = ?",
            (room_code,)
        ).fetchone()

        conn.close()

        if room is None:
            return "Room not found. Please check the room code."

        return redirect(url_for("room", room_code=room_code))

    return render_template("join_room.html")


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5001)
