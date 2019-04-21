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
    query2 = "SELECT followerUsername FROM Follow WHERE acceptedFollow = %s AND followeeUsername = %s"
    followee = session["username"]
    with connection.cursor() as cursor2:
        cursor2.execute(query2, (0, followee))
    requests = cursor2.fetchall()
    print(requests)
    return render_template("home.html", username=session["username"], requests=requests)

@app.route("/upload", methods=["GET"])
@login_required
def upload():
    return render_template("upload.html")


@app.route("/notifications", methods=["GET"])
@login_required
def notifications():
    getQuery = "SELECT followerUsername FROM Follow WHERE acceptedFollow=%s AND followeeUsername=%s"
    followee = session["username"]
    with connection.cursor() as cursor:
        cursor.execute(getQuery, (0, followee))
    followerRequests = cursor.fetchall()
    # print(followerRequests)
    query = "SELECT * FROM Tag NATURAL JOIN Photo WHERE (username=%s AND acceptedTag=%s)"
    with connection.cursor() as cursor:
        cursor.execute(query, (session["username"], 0))
    data = cursor.fetchall()
    return render_template("notifications.html", taggedNotifications=data, followerRequests=followerRequests)


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
    query2 = "SELECT * FROM Belong WHERE groupOwner=%s"
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
    if request.files:
        image_file = request.files.get("profilePic", "")
        image_name = image_file.filename
        filepath = os.path.join(IMAGES_DIR, image_name)
        image_file.save(filepath)
        requestData = request.form
        username = requestData["username"]
        plaintextPasword = requestData["password"]
        hashedPassword = hashlib.sha256(plaintextPasword.encode("utf-8")).hexdigest()
        firstName = requestData["fname"]
        lastName = requestData["lname"]
        bio = requestData["bio"]
        private = request.form.get("private")
        if (private=='yes'):
            private = 1
        else:
            private = 0
        try:
            with connection.cursor() as cursor:
                query = "INSERT INTO person (username, password, fname, lname, avatar, bio, isPrivate) VALUES (%s, %s, %s, %s, %s, %s, %r)"
                cursor.execute(query, (username, hashedPassword, firstName, lastName, image_name, bio, private))
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

    error = "Failed to upload image."
    return render_template("upload.html", error=error, username=session["username"])


@app.route("/taggedStatus", methods=["POST"])
@login_required
def taggedStatus():
    if request.form:
        # print(request.form['status'])
        # print(request.form['submit_button'])
        getQuery = "SELECT photoID FROM TAG WHERE (username=%s AND acceptedTag=%s)"
        with connection.cursor() as cursor:
            cursor.execute(getQuery, (session["username"], 0))
        data = cursor.fetchall()
        # print(data)
        currUser = session["username"]
        for photo in data:
            # print('status' + str(photo['photoID']))
            currStatus = request.form.get('status' + str(photo['photoID']))
            if (currStatus == "accept"):
                statusFlag = True
                queryT = "UPDATE Tag SET acceptedTag=%r WHERE (username=%s AND photoID=%s)"
                with connection.cursor() as cursor1:
                    cursor1.execute(queryT, (statusFlag, currUser, photo['photoID']))
            else:
                queryF = "DELETE FROM Tag WHERE (username=%s AND photoID=%s)"
                with connection.cursor() as cursor2:
                    cursor2.execute(queryF, (currUser, photo['photoID']))
    return render_template("notifications.html", username=session["username"])

@app.route("/createGroup", methods=["POST"])
@login_required
def createGroup():
    if request.form:
        requestData = request.form
        groupName = requestData["groupName"]
        groupOwner = session["username"]
        query = "INSERT INTO CloseFriendGroup (groupName, groupOwner) VALUES (%s, %s)"
        with connection.cursor() as cursor:
            cursor.execute(query, (groupName, groupOwner))
        message = "CloseFriendGroup has been successfully created."
        return render_template("groups.html", message=message, username=session["username"])
    else:
        message = "Failed to create CloseFriendGroup."
        return render_template("groups.html", message=message, username=session["username"])

@app.route("/addMember", methods=["POST"])
@login_required
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

@app.route("/follow", methods=["POST"])
@login_required
def follow():
    if request.form:
        requestData = request.form
        followee = requestData["followee"]
        follower = session["username"]
        acceptedFollow = 0

        try:
            query = "INSERT INTO Follow (followerUsername, followeeUsername, acceptedFollow) VALUES (%s, %s, %s)"
            with connection.cursor() as cursor:
                if follower != followee:
                    cursor.execute(query, (follower, followee, acceptedFollow))
                    message = "Follower request sent to " + followee
                else:
                    message = "You can't follow yourself!"
        except:
            message = "Failed to request follow for " + followee
        return render_template("home.html", message=message, username=session["username"])
    else:
        return render_template("home.html", username=session["username"])

@app.route("/followStatus", methods=["POST"])
@login_required
def followStatus():
    if request.form:
        followee = session["username"]

        getQuery = "SELECT followerUsername FROM Follow WHERE (followeeUsername=%s AND acceptedfollow=%s)"
        with connection.cursor() as cursor:
            cursor.execute(getQuery, (followee, 0))
        data = cursor.fetchall()
        print(data)

        for follower in data:
            currStatus = request.form["status" + follower["followerUsername"]]
            if currStatus == "accept":
                updateQuery = "UPDATE Follow SET acceptedFollow=%s WHERE followeeUsername=%s"
                with connection.cursor() as cursor:
                    cursor.execute(updateQuery, (1, followee))
            else:
                deleteQ = "DELETE FROM Follow WHERE followerUsername=%s"
                with connection.cursor() as cursor:
                    cursor.execute(deleteQ, (follower["followerUsername"]))

    return render_template("notifications.html", username=session["username"])

if __name__ == "__main__":
    if not os.path.isdir("images"):
        os.mkdir(IMAGES_DIR)
    app.run()
