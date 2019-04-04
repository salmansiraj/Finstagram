from flask import Flask, render_template, request, session, redirect, url_for, send_file
import os
import uuid
import hashlib
import pymysql.cursors
from functools import wraps
import time

app = Flask(__name__)
app.secret_key = "super secret key"
IMAGES_DIR = os.path.join(os.getcwd(), "images")

connection = pymysql.connect(host="localhost",
                             user="root",
                             password="root",
                             db="Finstagram",
                             charset="utf8mb4",
                             port=8889,
                             cursorclass=pymysql.cursors.DictCursor,
                             autocommit=True)

def login_required(f):
    @wraps(f)
    def dec(*args, **kwargs):
        if not "username" in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return dec

@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("home"))
    return render_template("index.html")

@app.route("/home")
@login_required
def home():
    return render_template("home.html", username=session["username"])

@app.route("/upload", methods=["GET"])
@login_required
def upload():
    return render_template("upload.html")


@app.route("/notifications", methods=["GET"])
@login_required
def notifications():
    query = "SELECT * FROM Tag NATURAL JOIN Photo WHERE username=%s"
    with connection.cursor() as cursor:
        cursor.execute(query, (session["username"]))
    data = cursor.fetchall()
    return render_template("notifications.html", taggedNotifications=data)

# @app.route("/images", methods=["GET"])
# @login_required
# def images():
#     groupOwner = session["username"]

#     query = "SELECT DISTINCT(photoID), timestamp, allFollowers, caption, filePath FROM photo NATURAL JOIN CloseFriendGroup WHERE (groupOwner=%s)"
#     # Who are the types of people that can see your photos?
#         # Yourself (done)
#         # The people in the groups that you own ?
#         # The people who follow you ONLY IF allFollowers = True
#         # etc...
#     with connection.cursor() as cursor:
#         cursor.execute(query, (groupOwner, groupOwner))
#     data = cursor.fetchall()
#     return render_template("images.html", images=data)


@app.route("/images", methods=["GET"])
@login_required
def images():
    query = "SELECT DISTINCT(photoID), timestamp, allFollowers, caption, filePath FROM photo NATURAL JOIN CloseFriendGroup WHERE (groupOwner=%s)"
    with connection.cursor() as cursor:
        cursor.execute(query, (session["username"]))
    data = cursor.fetchall()
    return render_template("images.html", images=data)


@app.route("/groups", methods=["GET"])
def groups():
    groupOwner = session["username"]
    query1 = "SELECT * FROM CloseFriendGroup WHERE groupOwner=%s"
    query2 = "SELECT * FROM Belong"
    with connection.cursor() as cursor1:
        cursor1.execute(query1, (groupOwner))
    with connection.cursor() as cursor2:
        cursor2.execute(query2)
    data1 = cursor1.fetchall()   
    data2 = cursor2.fetchall() 
    print(data2)
    return render_template("groups.html", groups=data1, users=data2, username=session["username"])


@app.route("/image/<image_name>", methods=["GET"])
def image(image_name):
    image_location = os.path.join(IMAGES_DIR, image_name)
    if os.path.isfile(image_location):
        return send_file(image_location, mimetype="image/jpg")

@app.route("/login", methods=["GET"])
def login():
    return render_template("login.html")

@app.route("/register", methods=["GET"])
def register():
    return render_template("register.html")


@app.route("/loginAuth", methods=["POST"])
def loginAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        plaintextPasword = requestData["password"]
        hashedPassword = hashlib.sha256(plaintextPasword.encode("utf-8")).hexdigest()

        with connection.cursor() as cursor:
            query = "SELECT * FROM person WHERE username = %s AND password = %s"
            cursor.execute(query, (username, hashedPassword))
        data = cursor.fetchone()
        if data:
            session["username"] = username
            return redirect(url_for("home"))

        error = "Incorrect username or password."
        return render_template("login.html", error=error)

    error = "An unknown error has occurred. Please try again."
    return render_template("login.html", error=error)

@app.route("/registerAuth", methods=["POST"])
def registerAuth():
    if request.form:
        requestData = request.form
        username = requestData["username"]
        plaintextPasword = requestData["password"]
        hashedPassword = hashlib.sha256(plaintextPasword.encode("utf-8")).hexdigest()
        firstName = requestData["fname"]
        lastName = requestData["lname"]
        
        try:
            with connection.cursor() as cursor:
                query = "INSERT INTO person (username, password, fname, lname) VALUES (%s, %s, %s, %s)"
                cursor.execute(query, (username, hashedPassword, firstName, lastName))
        except pymysql.err.IntegrityError:
            error = "%s is already taken." % (username)
            return render_template('register.html', error=error)    

        return redirect(url_for("login"))

    error = "An error has occurred. Please try again."
    return render_template("register.html", error=error)

@app.route("/logout", methods=["GET"])
def logout():
    session.pop("username")
    return redirect("/")


@app.route("/uploadImage", methods=["GET", "POST"])
@login_required
def upload_image():
    if request.files:
        image_file = request.files.get("imageToUpload", "")
        image_name = image_file.filename
        filepath = os.path.join(IMAGES_DIR, image_name)
        image_file.save(filepath)   
        caption = request.form["caption"]
        imageOwner = session["username"]
        taggedUser = request.form["taggedUser"]
        test = request.form.get("allFollowers")
        if (test):
            allFollowers = True
        else:
            allFollowers = False
        
        query1 = "INSERT INTO photo (timestamp, filePath, caption, allFollowers, photoOwner) VALUES (%s, %s, %s, %s, %s)"
        query2 = "INSERT INTO Tag (username, photoID, acceptedTag) VALUES (%s, %s, %r)"

        with connection.cursor() as cursor1:
            cursor1.execute(query1, (time.strftime('%Y-%m-%d %H:%M:%S'), image_name, caption, allFollowers, imageOwner))

        with connection.cursor() as cursor2:
            cursor2.execute(query2, (taggedUser, cursor1.lastrowid, False))

        message = "Image has been successfully uploaded."
        return render_template("upload.html", message=message, username=session["username"])
    else:
        message = "Failed to upload image."
        return render_template("upload.html", message=message, username=session["username"])


@app.route("/taggedStatus", methods=["POST"])
@login_required
def taggedStatus():
    if request.form:
        # print(request.form['status'])
        # print(request.form['submit_button'])
        getQuery = "SELECT photoID FROM TAG WHERE (username=%s)"
        with connection.cursor() as cursor:
            cursor.execute(getQuery, (session["username"]))
        data = cursor.fetchall()
        for photo in data:
            currStatus = request.form.get("status")
            currUser = session["username"]
            if (currStatus == "accept"):
                statusFlag = True
            else:
                statusFlag = False
            query = "UPDATE Tag SET acceptedTag=%r WHERE (username=%s AND photoID=%s)"
            with connection.cursor() as cursor:
                cursor.execute(query, (statusFlag,currUser, photo['photoID']))
    return render_template("notifications.html", username=session["username"])
        



@app.route("/createGroup", methods=["POST"])
def createGroup():
    if request.form:
        requestData = request.form
        groupName = requestData["groupName"]
        groupOwner = session["username"]
        query = "INSERT INTO CloseFriendGroup (groupName, groupOwner) VALUES (%s, %s)"
        with connection.cursor() as cursor:
            cursor.execute(query, (groupName, groupOwner))
        message = "CloseFriendGroup has been successfully uploaded."
        return render_template("groups.html", message=message, username=session["username"])
    else:
        message = "Failed to create CloseFriendGroup."
        return render_template("groups.html", message=message, username=session["username"])

@app.route("/addMember", methods=["POST"])
def addMember():
    if request.form:
        requestData = request.form
        groupName = requestData["groupName"]
        newMember = requestData["newMember"]
        owner = session["username"]
        try:
            query = "INSERT INTO Belong (groupName, groupOwner, username) VALUES (%s, %s, %s)"
            with connection.cursor() as cursor:
                cursor.execute(query, (groupName, owner, newMember))
            message = newMember + " has successfully been added to " + groupName
        except:
            message = "User is already in this closeFriendGroup..."
        return render_template("groups.html", message=message, username=session["username"])
    else:
        message = "Failed to add " + newMember + " to " + groupName
        return render_template("groups.html", message=message, username=session["username"])

if __name__ == "__main__":
    if not os.path.isdir("images"):
        os.mkdir(IMAGES_DIR)
    app.run()
